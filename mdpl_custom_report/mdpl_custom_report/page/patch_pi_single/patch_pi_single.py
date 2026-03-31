import frappe
import json
from frappe import _
from frappe.utils import now, getdate


# ------------------------------------------------------------------
# SINGLE Purchase Invoice
# ------------------------------------------------------------------

@frappe.whitelist()
def get_pi_details(pi_name):
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc("Purchase Invoice", pi_name)

    items = []
    for row in doc.items:
        items.append({
            "name": row.name,
            "idx": row.idx,
            "item_code": row.item_code,
            "item_name": row.item_name,
            "item_group": row.item_group or "",
            "qty": row.qty,
            "rate": row.rate,
            "amount": row.amount,
            "cost_center": row.cost_center or "",
            "expense_account": row.expense_account or "",
        })

    return {
        "pi_name": doc.name,
        "supplier": doc.supplier,
        "posting_date": str(doc.posting_date),
        "grand_total": doc.grand_total,
        "status": doc.status,
        "docstatus": doc.docstatus,
        "items": items,
    }


@frappe.whitelist()
def patch_pi_fields(pi_name, items, new_posting_date=None):
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(items, str):
        items = json.loads(items)

    doc = frappe.get_doc("Purchase Invoice", pi_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted Purchase Invoices can be patched via this tool."))

    all_changes = []

    # -- 1. Patch item-level fields (item_group, cost_center, expense_account) --
    item_changes = _apply_pi_patches(doc, items)
    all_changes.extend(item_changes)

    # -- 2. Patch posting date + sync GL entries --
    if new_posting_date:
        date_changes = _apply_posting_date_patch(doc, new_posting_date)
        all_changes.extend(date_changes)

    if not all_changes:
        return {"status": "no_changes", "message": "No changes detected."}

    _finalize("Purchase Invoice", pi_name, all_changes)

    return {
        "status": "success",
        "message": "Purchase Invoice updated successfully.",
        "changes": all_changes,
    }


# ------------------------------------------------------------------
# BULK Purchase Invoice
# ------------------------------------------------------------------

@frappe.whitelist()
def bulk_patch_pis(pi_names, item_group_map, cost_center_map):
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(pi_names, str):
        pi_names = json.loads(pi_names)
    if isinstance(item_group_map, str):
        item_group_map = json.loads(item_group_map)
    if isinstance(cost_center_map, str):
        cost_center_map = json.loads(cost_center_map)

    results = []
    errors = []
    success_count = 0
    skip_count = 0

    for pi_name in pi_names:
        try:
            doc = frappe.get_doc("Purchase Invoice", pi_name)

            if doc.docstatus != 1:
                skip_count += 1
                errors.append({"pi": pi_name, "error": "Not submitted (docstatus={0})".format(doc.docstatus)})
                continue

            items_patch = []
            for row in doc.items:
                patch = {"name": row.name}
                if row.item_code in item_group_map:
                    patch["item_group"] = item_group_map[row.item_code]
                if row.item_code in cost_center_map:
                    patch["cost_center"] = cost_center_map[row.item_code]
                if len(patch) > 1:
                    items_patch.append(patch)

            changes = _apply_pi_patches(doc, items_patch)

            if not changes:
                skip_count += 1
                results.append({"pi": pi_name, "changes": [], "status": "no_changes"})
                continue

            _finalize("Purchase Invoice", pi_name, changes)
            success_count += 1
            results.append({"pi": pi_name, "changes": changes, "status": "success"})

        except Exception as e:
            errors.append({"pi": pi_name, "error": str(e)})

    return {"success_count": success_count, "skip_count": skip_count, "errors": errors, "results": results}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _apply_pi_patches(doc, items):
    """Patch item_group, cost_center, and expense_account on PI items and linked GL entries."""
    changes = []
    item_map = {row.name: row for row in doc.items}

    for incoming in items:
        row_name = incoming.get("name")
        if not row_name or row_name not in item_map:
            continue
        row = item_map[row_name]

        # -- item_group --
        new_group = (incoming.get("item_group") or "").strip()
        if new_group and (row.item_group or "") != new_group:
            frappe.db.set_value(
                "Purchase Invoice Item", row_name, "item_group", new_group,
                update_modified=False
            )
            changes.append("Item #{0} ({1}): item_group '{2}' ? '{3}'".format(
                row.idx, row.item_code, row.item_group or "", new_group))

        # -- cost_center --
        new_cc = (incoming.get("cost_center") or "").strip()
        if new_cc and (row.cost_center or "") != new_cc:
            frappe.db.set_value(
                "Purchase Invoice Item", row_name, "cost_center", new_cc,
                update_modified=False
            )
            # Sync cost_center on GL entries for this PI + account + old cost_center
            _sync_gl_cost_center(doc.name, row.expense_account or "", row.cost_center or "", new_cc)
            changes.append("Item #{0} ({1}): cost_center '{2}' ? '{3}'".format(
                row.idx, row.item_code, row.cost_center or "", new_cc))

        # -- expense_account --
        new_account = (incoming.get("expense_account") or "").strip()
        if new_account and (row.expense_account or "") != new_account:
            # Validate account exists
            if not frappe.db.exists("Account", new_account):
                frappe.throw(_("Account '{0}' does not exist.").format(new_account))

            old_account = row.expense_account or ""

            # Update PI item row
            frappe.db.set_value(
                "Purchase Invoice Item", row_name, "expense_account", new_account,
                update_modified=False
            )

            # Remap GL entries: old account ? new account for this voucher
            _remap_gl_account(doc.name, old_account, new_account)

            changes.append("Item #{0} ({1}): expense_account '{2}' ? '{3}'".format(
                row.idx, row.item_code, old_account, new_account))

    return changes


def _apply_posting_date_patch(doc, new_posting_date):
    """Change posting_date on the PI and update all linked GL entries."""
    changes = []

    try:
        new_date = getdate(new_posting_date)
    except Exception:
        frappe.throw(_("Invalid posting date: {0}").format(new_posting_date))

    old_date = doc.posting_date
    if str(old_date) == str(new_date):
        return changes

    # Update Purchase Invoice header
    frappe.db.set_value(
        "Purchase Invoice", doc.name,
        {
            "posting_date": new_date,
            "due_date": new_date,       # recalc if needed; adjust to your business logic
        },
        update_modified=False,
    )

    # Update all GL Entries linked to this voucher
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET    posting_date = %(new_date)s
        WHERE  voucher_type = 'Purchase Invoice'
          AND  voucher_no   = %(voucher)s
    """, {"new_date": new_date, "voucher": doc.name})

    # Update Payment Ledger Entries (ERPNext v14+)
    frappe.db.sql("""
        UPDATE `tabPayment Ledger Entry`
        SET    posting_date = %(new_date)s
        WHERE  voucher_type = 'Purchase Invoice'
          AND  voucher_no   = %(voucher)s
    """, {"new_date": new_date, "voucher": doc.name})

    changes.append("posting_date '{0}' ? '{1}' (GL entries updated)".format(old_date, new_date))
    return changes


def _sync_gl_cost_center(voucher_no, account, old_cc, new_cc):
    """Update cost_center in GL Entry rows for a specific account on this voucher."""
    if not account:
        return
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET    cost_center = %(new_cc)s
        WHERE  voucher_type = 'Purchase Invoice'
          AND  voucher_no   = %(voucher)s
          AND  account      = %(account)s
          AND  (cost_center = %(old_cc)s OR cost_center IS NULL)
    """, {"new_cc": new_cc, "voucher": voucher_no, "account": account, "old_cc": old_cc})


def _remap_gl_account(voucher_no, old_account, new_account):
    """Remap account in GL Entry rows for this voucher (old ? new)."""
    if not old_account or not new_account or old_account == new_account:
        return
    frappe.db.sql("""
        UPDATE `tabGL Entry`
        SET    account = %(new_account)s
        WHERE  voucher_type = 'Purchase Invoice'
          AND  voucher_no   = %(voucher)s
          AND  account      = %(old_account)s
    """, {"new_account": new_account, "voucher": voucher_no, "old_account": old_account})


def _finalize(doctype, doc_name, changes):
    frappe.db.set_value(doctype, doc_name, "modified", now(), update_modified=False)
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": doctype,
        "reference_name": doc_name,
        "content": "<b>Fields patched on submitted {0} by {1}:</b><br>".format(
            doctype, frappe.session.user) + "<br>".join(changes),
    }).insert(ignore_permissions=True)
    frappe.db.commit()