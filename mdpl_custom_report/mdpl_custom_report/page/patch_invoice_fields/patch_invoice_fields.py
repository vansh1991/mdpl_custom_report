# -*- coding: utf-8 -*-
import frappe
import json
from frappe import _
from frappe.utils import now, getdate


@frappe.whitelist()
def get_invoice_details(invoice_name):
    if not frappe.has_permission("Sales Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc("Sales Invoice", invoice_name)

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
        })

    sales_team = []
    for row in (doc.sales_team or []):
        sales_team.append({
            "name": row.name,
            "idx": row.idx,
            "sales_person": row.sales_person,
            "allocated_percentage": row.allocated_percentage,
            "allocated_amount": row.allocated_amount,
            "incentives": row.incentives,
        })

    all_sales_persons = frappe.get_all(
        "Sales Person",
        fields=["name", "sales_person_name"],
        filters={"enabled": 1},
        ignore_permissions=True,
        order_by="name asc",
        limit=500,
    )

    # Fetch payment terms templates for dropdown
    payment_terms_list = frappe.get_all(
        "Payment Terms Template",
        fields=["name"],
        order_by="name asc",
    )

    return {
        "invoice_name":      doc.name,
        "customer":          doc.customer,
        "posting_date":      str(doc.posting_date),
        "due_date":          str(doc.due_date) if doc.due_date else "",
        "payment_terms_template": doc.payment_terms_template or "",
        "grand_total":       doc.grand_total,
        "status":            doc.status,
        "docstatus":         doc.docstatus,
        "items":             items,
        "sales_team":        sales_team,
        "all_sales_persons": all_sales_persons,
        "payment_terms_list": payment_terms_list,
    }


@frappe.whitelist()
def get_all_sales_persons():
    if not frappe.has_permission("Sales Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    return frappe.get_all(
        "Sales Person",
        fields=["name", "sales_person_name"],
        filters={"enabled": 1},
        ignore_permissions=True,
        order_by="name asc",
        limit=500,
    )


@frappe.whitelist()
def patch_invoice_fields(invoice_name, items, sales_team,
                         new_due_date=None, new_payment_terms=None):
    if not frappe.has_permission("Sales Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(items, str):
        items = json.loads(items)
    if isinstance(sales_team, str):
        sales_team = json.loads(sales_team)

    doc = frappe.get_doc("Sales Invoice", invoice_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted invoices can be patched via this tool."))

    changes = []

    # ----------------------------------------------------------------
    # 1. Patch due date
    # ----------------------------------------------------------------
    if new_due_date and new_due_date.strip():
        try:
            new_date_val = getdate(new_due_date.strip())
        except Exception:
            frappe.throw(_("Invalid due date: {0}").format(new_due_date))

        old_due = doc.due_date
        if str(old_due) != str(new_date_val):
            frappe.db.set_value(
                "Sales Invoice", invoice_name, "due_date", new_date_val,
                update_modified=False
            )
            # Also update Payment Ledger Entry due date
            frappe.db.sql("""
                UPDATE `tabPayment Ledger Entry`
                SET    due_date = %(new_date)s
                WHERE  voucher_type = 'Sales Invoice'
                  AND  voucher_no   = %(inv)s
            """, {"new_date": new_date_val, "inv": invoice_name})
            changes.append(
                "due_date: '{0}' -> '{1}'".format(old_due, new_date_val)
            )

    # ----------------------------------------------------------------
    # 2. Patch payment terms template
    # ----------------------------------------------------------------
    if new_payment_terms is not None and new_payment_terms.strip() != (doc.payment_terms_template or ""):
        new_pt = new_payment_terms.strip()
        old_pt = doc.payment_terms_template or ""

        # Validate template exists (allow clearing with empty string)
        if new_pt and not frappe.db.exists("Payment Terms Template", new_pt):
            frappe.throw(_("Payment Terms Template '{0}' does not exist.").format(new_pt))

        frappe.db.set_value(
            "Sales Invoice", invoice_name, "payment_terms_template", new_pt or None,
            update_modified=False
        )
        changes.append(
            "payment_terms_template: '{0}' -> '{1}'".format(old_pt, new_pt or "(cleared)")
        )

    # ----------------------------------------------------------------
    # 3. Patch item groups
    # ----------------------------------------------------------------
    item_map = {row.name: row for row in doc.items}
    for incoming in items:
        row_name  = incoming.get("name")
        new_group = (incoming.get("item_group") or "").strip()
        if row_name and row_name in item_map:
            old_group = item_map[row_name].item_group or ""
            if old_group != new_group:
                frappe.db.set_value(
                    "Sales Invoice Item", row_name, "item_group", new_group,
                    update_modified=False,
                )
                changes.append(
                    "Item #{idx} ({item}): item_group '{old}' -> '{new}'".format(
                        idx=item_map[row_name].idx,
                        item=item_map[row_name].item_code,
                        old=old_group, new=new_group,
                    )
                )

    # ----------------------------------------------------------------
    # 4. Patch sales team
    # ----------------------------------------------------------------
    st_map = {row.name: row for row in (doc.sales_team or [])}
    incoming_names = set()

    for incoming in sales_team:
        row_name = incoming.get("name") or ""
        new_sp   = (incoming.get("sales_person") or "").strip()
        new_pct  = float(incoming.get("allocated_percentage") or 0)

        if row_name and row_name in st_map:
            incoming_names.add(row_name)
            old_sp  = st_map[row_name].sales_person or ""
            old_pct = float(st_map[row_name].allocated_percentage or 0)
            field_changes = []

            if old_sp != new_sp:
                frappe.db.sql(
                    "UPDATE `tabSales Team` SET sales_person=%s WHERE name=%s",
                    (new_sp, row_name)
                )
                field_changes.append("sales_person: '{0}' -> '{1}'".format(old_sp, new_sp))

            if abs(old_pct - new_pct) > 0.001:
                allocated_amount = (new_pct / 100.0) * doc.grand_total
                frappe.db.set_value(
                    "Sales Team", row_name,
                    {"allocated_percentage": new_pct, "allocated_amount": allocated_amount},
                    update_modified=False,
                )
                field_changes.append(
                    "allocated_percentage: {0}% -> {1}%".format(old_pct, new_pct)
                )

            if field_changes:
                changes.append(
                    "Sales Team row #{0}: ".format(st_map[row_name].idx)
                    + ", ".join(field_changes)
                )
        else:
            if not new_sp:
                continue
            new_name = frappe.generate_hash("Sales Team", 10)
            allocated_amount = (new_pct / 100.0) * doc.grand_total
            frappe.db.sql("""
                INSERT INTO `tabSales Team`
                    (name, creation, modified, modified_by, owner,
                     docstatus, parenttype, parentfield, parent,
                     sales_person, allocated_percentage, allocated_amount)
                VALUES (%s, NOW(), NOW(), %s, %s, 0,
                        'Sales Invoice', 'sales_team', %s, %s, %s, %s)
            """, (
                new_name, frappe.session.user, frappe.session.user,
                invoice_name, new_sp, new_pct, allocated_amount
            ))
            incoming_names.add(new_name)
            changes.append("Sales Team: added '{0}' at {1}%".format(new_sp, new_pct))

    for row_name, row in st_map.items():
        if row_name not in incoming_names:
            frappe.db.delete("Sales Team", {"name": row_name})
            changes.append("Sales Team: removed '{0}'".format(row.sales_person))

    if not changes:
        return {"status": "no_changes", "message": "No changes detected."}

    frappe.db.set_value(
        "Sales Invoice", invoice_name, "modified", now(), update_modified=False
    )
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice_name,
        "content": "<b>Fields patched on submitted invoice by {0}:</b><br>".format(
            frappe.session.user
        ) + "<br>".join(changes),
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status":  "success",
        "message": "Invoice updated successfully.",
        "changes": changes,
    }


@frappe.whitelist()
def bulk_patch_invoices(invoice_names, sales_team, item_group_map):
    if not frappe.has_permission("Sales Invoice", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(invoice_names, str):
        invoice_names = json.loads(invoice_names)
    if isinstance(sales_team, str):
        sales_team = json.loads(sales_team)
    if isinstance(item_group_map, str):
        item_group_map = json.loads(item_group_map)

    results = []
    errors  = []
    success_count = 0
    skip_count    = 0

    for inv_name in invoice_names:
        try:
            doc = frappe.get_doc("Sales Invoice", inv_name)

            if doc.docstatus != 1:
                skip_count += 1
                errors.append({"invoice": inv_name,
                                "error": "Not submitted (docstatus={0})".format(doc.docstatus)})
                continue

            items_patch = []
            for row in doc.items:
                if row.item_code in item_group_map:
                    items_patch.append({"name": row.name,
                                        "item_group": item_group_map[row.item_code]})

            if sales_team:
                st_patch = [{"name": "", "sales_person": st.get("sales_person", ""),
                              "allocated_percentage": float(st.get("allocated_percentage", 0))}
                            for st in sales_team]
            else:
                st_patch = [{"name": row.name, "sales_person": row.sales_person,
                              "allocated_percentage": float(row.allocated_percentage or 0)}
                            for row in (doc.sales_team or [])]

            changes = _apply_patches(doc, items_patch, st_patch)

            if not changes:
                skip_count += 1
                results.append({"invoice": inv_name, "changes": [], "status": "no_changes"})
                continue

            frappe.db.set_value("Sales Invoice", inv_name, "modified",
                                now(), update_modified=False)
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Sales Invoice",
                "reference_name": inv_name,
                "content": "<b>Fields patched by {0}:</b><br>".format(frappe.session.user)
                           + "<br>".join(changes),
            }).insert(ignore_permissions=True)
            frappe.db.commit()

            success_count += 1
            results.append({"invoice": inv_name, "changes": changes, "status": "success"})

        except Exception as e:
            errors.append({"invoice": inv_name, "error": str(e)})

    return {"success_count": success_count, "skip_count": skip_count,
            "errors": errors, "results": results}


def _apply_patches(doc, items, sales_team):
    changes = []
    parent_name = doc.name

    item_map = {row.name: row for row in doc.items}
    for incoming in items:
        row_name  = incoming.get("name")
        new_group = (incoming.get("item_group") or "").strip()
        if row_name and row_name in item_map:
            old_group = item_map[row_name].item_group or ""
            if old_group != new_group:
                frappe.db.set_value("Sales Invoice Item", row_name, "item_group",
                                    new_group, update_modified=False)
                changes.append(
                    "Item #{idx} ({item}): item_group '{old}' -> '{new}'".format(
                        idx=item_map[row_name].idx, item=item_map[row_name].item_code,
                        old=old_group, new=new_group
                    )
                )

    st_map = {row.name: row for row in (doc.sales_team or [])}
    incoming_names = set()

    for incoming in sales_team:
        row_name = incoming.get("name") or ""
        new_sp   = (incoming.get("sales_person") or "").strip()
        new_pct  = float(incoming.get("allocated_percentage") or 0)

        if row_name and row_name in st_map:
            incoming_names.add(row_name)
            old_sp  = st_map[row_name].sales_person or ""
            old_pct = float(st_map[row_name].allocated_percentage or 0)
            field_changes = []

            if old_sp != new_sp:
                frappe.db.sql("UPDATE `tabSales Team` SET sales_person=%s WHERE name=%s",
                              (new_sp, row_name))
                field_changes.append("sales_person: '{0}' -> '{1}'".format(old_sp, new_sp))

            if abs(old_pct - new_pct) > 0.001:
                allocated_amount = (new_pct / 100.0) * doc.grand_total
                frappe.db.set_value("Sales Team", row_name,
                                    {"allocated_percentage": new_pct,
                                     "allocated_amount": allocated_amount},
                                    update_modified=False)
                field_changes.append(
                    "allocated_percentage: {0}% -> {1}%".format(old_pct, new_pct)
                )

            if field_changes:
                changes.append(
                    "Sales Team row #{0}: ".format(st_map[row_name].idx)
                    + ", ".join(field_changes)
                )
        else:
            if not new_sp:
                continue
            new_name = frappe.generate_hash("Sales Team", 10)
            frappe.db.sql("""
                INSERT INTO `tabSales Team`
                    (name, creation, modified, modified_by, owner,
                     docstatus, parenttype, parentfield, parent,
                     sales_person, allocated_percentage, allocated_amount)
                VALUES (%s, NOW(), NOW(), %s, %s, 0,
                        'Sales Invoice', 'sales_team', %s, %s, %s, %s)
            """, (new_name, frappe.session.user, frappe.session.user,
                  parent_name, new_sp, new_pct, (new_pct / 100.0) * doc.grand_total))
            incoming_names.add(new_name)
            changes.append("Sales Team: added '{0}' at {1}%".format(new_sp, new_pct))

    for row_name, row in st_map.items():
        if row_name not in incoming_names:
            frappe.db.delete("Sales Team", {"name": row_name})
            changes.append("Sales Team: removed '{0}'".format(row.sales_person))

    return changes