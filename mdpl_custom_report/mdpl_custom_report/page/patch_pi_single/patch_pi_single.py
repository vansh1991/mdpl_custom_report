import frappe
import json
from frappe import _
from frappe.utils import now


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
def patch_pi_fields(pi_name, items):
    if not frappe.has_permission("Purchase Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(items, str):
        items = json.loads(items)

    doc = frappe.get_doc("Purchase Invoice", pi_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted Purchase Invoices can be patched via this tool."))

    changes = _apply_pi_patches(doc, items)

    if not changes:
        return {"status": "no_changes", "message": "No changes detected."}

    _finalize("Purchase Invoice", pi_name, changes)

    return {"status": "success", "message": "Purchase Invoice updated successfully.", "changes": changes}


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
    changes = []
    item_map = {row.name: row for row in doc.items}

    for incoming in items:
        row_name = incoming.get("name")
        if not row_name or row_name not in item_map:
            continue
        row = item_map[row_name]

        new_group = (incoming.get("item_group") or "").strip()
        if new_group and (row.item_group or "") != new_group:
            frappe.db.set_value("Purchase Invoice Item", row_name, "item_group", new_group, update_modified=False)
            changes.append("Item #{0} ({1}): item_group '{2}' -> '{3}'".format(
                row.idx, row.item_code, row.item_group or "", new_group))

        new_cc = (incoming.get("cost_center") or "").strip()
        if new_cc and (row.cost_center or "") != new_cc:
            frappe.db.set_value("Purchase Invoice Item", row_name, "cost_center", new_cc, update_modified=False)
            changes.append("Item #{0} ({1}): cost_center '{2}' -> '{3}'".format(
                row.idx, row.item_code, row.cost_center or "", new_cc))

    return changes


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