import frappe
from frappe.utils import nowdate

@frappe.whitelist()
def create_purchase_order(data):
    """
    Create a Purchase Order in ERPNext.
    """
    import json

    try:
        if isinstance(data, str):
            data = json.loads(data)

        supplier = data.get("supplier")
        items = data.get("items", [])
        schedule_date = data.get("schedule_date", nowdate())

        if not supplier or not items:
            return {"error": "Missing supplier or items."}

        # Create new Purchase Order doc
        po = frappe.new_doc("Purchase Order")
        po.supplier = supplier
        po.schedule_date = schedule_date

        for item in items:
            po.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "schedule_date": item.get("schedule_date") or schedule_date,
            })

        po.insert(ignore_permissions=True)
        po.submit()

        return {
            "message": f"Purchase Order {po.name} created successfully.",
            "purchase_order": po.name,
            "url": f"/app/purchase-order/{po.name}"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Order Error")
        return {"error": str(e)}
