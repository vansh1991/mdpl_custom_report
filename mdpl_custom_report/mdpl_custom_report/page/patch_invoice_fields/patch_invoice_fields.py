import frappe
import json
from frappe import _
from frappe.utils import now


@frappe.whitelist()
def get_invoice_details(invoice_name):
    """
    Fetch current item groups, sales persons and basic info
    for a submitted Sales Invoice.
    """
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

    # Fetch ALL sales persons ignoring user-level link permissions
    # (Sales Person is linked to Employee; users can normally only see
    #  their own -- this bypasses that restriction safely.)
    all_sales_persons = frappe.get_all(
        "Sales Person",
        fields=["name", "sales_person_name"],
        filters={"enabled": 1},
        ignore_permissions=True,
        order_by="name asc",
        limit=500,
    )

    return {
        "invoice_name": doc.name,
        "customer": doc.customer,
        "posting_date": str(doc.posting_date),
        "grand_total": doc.grand_total,
        "status": doc.status,
        "docstatus": doc.docstatus,
        "items": items,
        "sales_team": sales_team,
        "all_sales_persons": all_sales_persons,
    }


@frappe.whitelist()
def get_all_sales_persons():
    """
    Return all active Sales Persons regardless of user link permissions.
    Called on page load to populate the Sales Person dropdown.
    """
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
def patch_invoice_fields(invoice_name, items, sales_team):
    """
    Directly update item_group on Sales Invoice Item rows and
    sales_person / allocated_percentage on Sales Team rows for a
    submitted (docstatus=1) Sales Invoice.

    Uses ignore_permissions / raw SQL for Sales Team writes so that
    any sales person can be assigned regardless of the logged-in
    user's Employee link restriction.

    A comment is added to the document timeline for full audit trail.
    """
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
    # Patch item groups
    # ----------------------------------------------------------------
    item_map = {row.name: row for row in doc.items}
    for incoming in items:
        row_name = incoming.get("name")
        new_group = (incoming.get("item_group") or "").strip()
        if row_name and row_name in item_map:
            old_group = item_map[row_name].item_group or ""
            if old_group != new_group:
                frappe.db.set_value(
                    "Sales Invoice Item",
                    row_name,
                    "item_group",
                    new_group,
                    update_modified=False,
                )
                changes.append(
                    "Item #{idx} ({item}): item_group changed from '{old}' to '{new}'".format(
                        idx=item_map[row_name].idx,
                        item=item_map[row_name].item_code,
                        old=old_group,
                        new=new_group,
                    )
                )

    # ----------------------------------------------------------------
    # Patch sales team
    # ----------------------------------------------------------------
    st_map = {row.name: row for row in (doc.sales_team or [])}
    incoming_names = set()

    for incoming in sales_team:
        row_name = incoming.get("name") or ""
        new_sp  = (incoming.get("sales_person") or "").strip()
        new_pct = float(incoming.get("allocated_percentage") or 0)

        if row_name and row_name in st_map:
            # - Update existing row -
            incoming_names.add(row_name)
            old_sp  = st_map[row_name].sales_person or ""
            old_pct = float(st_map[row_name].allocated_percentage or 0)
            field_changes = []

            if old_sp != new_sp:
                # Use raw SQL so Frappe does NOT run a link-permission
                # check on the Sales Person field value.
                frappe.db.sql(
                    "UPDATE `tabSales Team` SET sales_person=%s WHERE name=%s",
                    (new_sp, row_name)
                )
                field_changes.append(
                    "sales_person: '{old}' -> '{new}'".format(old=old_sp, new=new_sp)
                )

            if abs(old_pct - new_pct) > 0.001:
                allocated_amount = (new_pct / 100.0) * doc.grand_total
                frappe.db.set_value(
                    "Sales Team",
                    row_name,
                    {
                        "allocated_percentage": new_pct,
                        "allocated_amount": allocated_amount,
                    },
                    update_modified=False,
                )
                field_changes.append(
                    "allocated_percentage: {old}% -> {new}%".format(
                        old=old_pct, new=new_pct
                    )
                )

            if field_changes:
                changes.append(
                    "Sales Team row #{idx}: ".format(idx=st_map[row_name].idx)
                    + ", ".join(field_changes)
                )

        else:
            # - Insert new row via raw SQL to skip link validation -
            if not new_sp:
                continue
            new_name = frappe.generate_hash("Sales Team", 10)
            allocated_amount = (new_pct / 100.0) * doc.grand_total
            frappe.db.sql("""
                INSERT INTO `tabSales Team`
                    (name, creation, modified, modified_by, owner,
                     docstatus, parenttype, parentfield, parent,
                     sales_person, allocated_percentage, allocated_amount)
                VALUES (
                    %s, NOW(), NOW(), %s, %s,
                    0, 'Sales Invoice', 'sales_team', %s,
                    %s, %s, %s
                )
            """, (
                new_name, frappe.session.user, frappe.session.user,
                invoice_name, new_sp, new_pct, allocated_amount
            ))
            incoming_names.add(new_name)
            changes.append(
                "Sales Team: added '{sp}' at {pct}%".format(sp=new_sp, pct=new_pct)
            )

    # Delete rows removed in the UI
    for row_name, row in st_map.items():
        if row_name not in incoming_names:
            frappe.db.delete("Sales Team", {"name": row_name})
            changes.append(
                "Sales Team: removed '{sp}'".format(sp=row.sales_person)
            )

    if not changes:
        return {"status": "no_changes", "message": "No changes detected."}

    # Update parent modified timestamp
    frappe.db.set_value(
        "Sales Invoice",
        invoice_name,
        "modified",
        now(),
        update_modified=False,
    )

    # Audit trail comment
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice_name,
        "content": "<b>Fields patched on submitted invoice by {user}:</b><br>".format(
            user=frappe.session.user
        ) + "<br>".join(changes),
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Invoice updated successfully.",
        "changes": changes,
    }


@frappe.whitelist()
def bulk_patch_invoices(invoice_names, sales_team, item_group_map):
    """Bulk version -- same permission fix applied to all invoices."""
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

            # Build item patch list
            items_patch = []
            for row in doc.items:
                if row.item_code in item_group_map:
                    items_patch.append({"name": row.name,
                                        "item_group": item_group_map[row.item_code]})

            # Sales team -- use the supplied team or keep existing
            if sales_team:
                st_patch = [{"name": "", "sales_person": st.get("sales_person",""),
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


# - Internal helpers -

def _apply_patches(doc, items, sales_team):
    """Shared patch logic -- used by bulk."""
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
                changes.append("Item #{idx} ({item}): item_group '{old}' -> '{new}'".format(
                    idx=item_map[row_name].idx, item=item_map[row_name].item_code,
                    old=old_group, new=new_group))

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
                field_changes.append("allocated_percentage: {0}% -> {1}%".format(old_pct, new_pct))

            if field_changes:
                changes.append("Sales Team row #{0}: ".format(st_map[row_name].idx)
                               + ", ".join(field_changes))
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