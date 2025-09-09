import frappe
from frappe.utils import nowdate
import json
from datetime import date

def convert_dates(obj):
    if isinstance(obj, dict):
        return {k: convert_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates(i) for i in obj]
    elif isinstance(obj, date):
        return obj.isoformat()
    else:
        return obj

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

        # Convert dates to strings before logging
        safe_columns = convert_dates(columns)
        safe_data = convert_dates(data)

        frappe.log_error(json.dumps({
            "columns": safe_columns,
            "data": safe_data
        }), "Sales Order Report Debug")

        return {
            "message": f"Generate Sales Order Analysis report from {from_date} to {to_date}",
            "columns": safe_columns,
            "data": safe_data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Order Report Error")
        return {"error": str(e)}
