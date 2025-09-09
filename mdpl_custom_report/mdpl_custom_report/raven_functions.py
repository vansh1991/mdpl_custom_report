import frappe
from frappe.utils import nowdate
import json

@frappe.whitelist()
def generate_sales_order_analysis(from_date=None, to_date=None):
    if not from_date:
        from_date = nowdate()
    if not to_date:
        to_date = nowdate()

    report_name = "Sales Order Analysis"
    filters = {"from_date": from_date, "to_date": to_date}

    try:
        report = frappe.get_doc("Report", report_name)
        columns, data = report.get_data(filters=filters, as_dict=True)

        frappe.log_error(json.dumps({
            "columns": columns,
            "data": data
        }), "Sales Order Report Debug")

        return {
            "message": f"Generate Sales Order Analysis report from {from_date} to {to_date}",
            "columns": columns,
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Order Report Error")
        return {"error": str(e)}
