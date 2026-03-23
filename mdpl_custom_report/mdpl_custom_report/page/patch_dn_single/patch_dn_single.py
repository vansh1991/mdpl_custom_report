import frappe
import json
from frappe import _
from frappe.utils import now


# ------------------------------------------------------------------
# SINGLE DN
# ------------------------------------------------------------------

@frappe.whitelist()
def get_dn_details(dn_name):
    if not frappe.has_permission("Delivery Note", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc("Delivery Note", dn_name)

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
            "warehouse": row.warehouse or "",
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

    return {
        "dn_name": doc.name,
        "customer": doc.customer,
        "posting_date": str(doc.posting_date),
        "grand_total": doc.grand_total,
        "status": doc.status,
        "docstatus": doc.docstatus,
        "items": items,
        "sales_team": sales_team,
    }


@frappe.whitelist()
def patch_dn_fields(dn_name, items, sales_team):
    if not frappe.has_permission("Delivery Note", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(items, str):
        items = json.loads(items)
    if isinstance(sales_team, str):
        sales_team = json.loads(sales_team)

    doc = frappe.get_doc("Delivery Note", dn_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted Delivery Notes can be patched via this tool."))

    changes = _apply_patches(doc, items, sales_team)

    if not changes:
        return {"status": "no_changes", "message": "No changes detected."}

    _finalize_dn(dn_name, changes)

    return {
        "status": "success",
        "message": "Delivery Note updated successfully.",
        "changes": changes,
    }


# ------------------------------------------------------------------
# BULK DN
# ------------------------------------------------------------------

@frappe.whitelist()
def bulk_patch_dns(dn_names, sales_team, item_group_map):
    if not frappe.has_permission("Delivery Note", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(dn_names, str):
        dn_names = json.loads(dn_names)
    if isinstance(sales_team, str):
        sales_team = json.loads(sales_team)
    if isinstance(item_group_map, str):
        item_group_map = json.loads(item_group_map)

    results = []
    errors = []
    success_count = 0
    skip_count = 0

    for dn_name in dn_names:
        try:
            doc = frappe.get_doc("Delivery Note", dn_name)

            if doc.docstatus != 1:
                skip_count += 1
                errors.append({
                    "dn": dn_name,
                    "error": "Not submitted (docstatus={0})".format(doc.docstatus),
                })
                continue

            items_patch = []
            for row in doc.items:
                if row.item_code in item_group_map:
                    items_patch.append({
                        "name": row.name,
                        "item_group": item_group_map[row.item_code],
                    })

            if sales_team:
                st_patch = [
                    {
                        "name": "",
                        "sales_person": st.get("sales_person", ""),
                        "allocated_percentage": float(st.get("allocated_percentage", 0)),
                    }
                    for st in sales_team
                ]
            else:
                st_patch = [
                    {
                        "name": row.name,
                        "sales_person": row.sales_person,
                        "allocated_percentage": float(row.allocated_percentage or 0),
                    }
                    for row in (doc.sales_team or [])
                ]

            changes = _apply_patches(doc, items_patch, st_patch)

            if not changes:
                skip_count += 1
                results.append({"dn": dn_name, "changes": [], "status": "no_changes"})
                continue

            _finalize_dn(dn_name, changes)
            success_count += 1
            results.append({"dn": dn_name, "changes": changes, "status": "success"})

        except Exception as e:
            errors.append({"dn": dn_name, "error": str(e)})

    return {
        "success_count": success_count,
        "skip_count": skip_count,
        "errors": errors,
        "results": results,
    }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _apply_patches(doc, items, sales_team):
    changes = []
    parent_name = doc.name

    item_map = {row.name: row for row in doc.items}
    for incoming in items:
        row_name = incoming.get("name")
        new_group = (incoming.get("item_group") or "").strip()
        if row_name and row_name in item_map:
            old_group = item_map[row_name].item_group or ""
            if old_group != new_group:
                frappe.db.set_value(
                    "Delivery Note Item", row_name, "item_group",
                    new_group, update_modified=False,
                )
                changes.append(
                    "Item #{0} ({1}): item_group '{2}' -> '{3}'".format(
                        item_map[row_name].idx,
                        item_map[row_name].item_code,
                        old_group, new_group,
                    )
                )

    st_map = {row.name: row for row in (doc.sales_team or [])}
    incoming_names = set()

    for incoming in sales_team:
        row_name = incoming.get("name") or ""
        new_sp = (incoming.get("sales_person") or "").strip()
        new_pct = float(incoming.get("allocated_percentage") or 0)

        if row_name and row_name in st_map:
            incoming_names.add(row_name)
            old_sp = st_map[row_name].sales_person or ""
            old_pct = float(st_map[row_name].allocated_percentage or 0)
            field_changes = []

            if old_sp != new_sp:
                frappe.db.set_value("Sales Team", row_name, "sales_person", new_sp, update_modified=False)
                field_changes.append("sales_person: '{0}' -> '{1}'".format(old_sp, new_sp))

            if abs(old_pct - new_pct) > 0.001:
                allocated_amount = (new_pct / 100.0) * doc.grand_total
                frappe.db.set_value(
                    "Sales Team", row_name,
                    {"allocated_percentage": new_pct, "allocated_amount": allocated_amount},
                    update_modified=False,
                )
                field_changes.append("allocated_percentage: {0}% -> {1}%".format(old_pct, new_pct))

            if field_changes:
                changes.append(
                    "Sales Team row #{0}: ".format(st_map[row_name].idx) + ", ".join(field_changes)
                )
        else:
            if not new_sp:
                continue
            new_row = frappe.get_doc({
                "doctype": "Sales Team",
                "parenttype": "Delivery Note",
                "parentfield": "sales_team",
                "parent": parent_name,
                "sales_person": new_sp,
                "allocated_percentage": new_pct,
                "allocated_amount": (new_pct / 100.0) * doc.grand_total,
            })
            new_row.db_insert()
            incoming_names.add(new_row.name)
            changes.append("Sales Team: added '{0}' at {1}%".format(new_sp, new_pct))

    for row_name, row in st_map.items():
        if row_name not in incoming_names:
            frappe.db.delete("Sales Team", {"name": row_name})
            changes.append("Sales Team: removed '{0}'".format(row.sales_person))

    return changes


def _finalize_dn(dn_name, changes):
    frappe.db.set_value("Delivery Note", dn_name, "modified", now(), update_modified=False)
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Delivery Note",
        "reference_name": dn_name,
        "content": "<b>Fields patched on submitted Delivery Note by {0}:</b><br>".format(
            frappe.session.user
        ) + "<br>".join(changes),
    }).insert(ignore_permissions=True)
    frappe.db.commit()