import frappe
from frappe.utils import nowdate
from frappe.utils.xlsxutils import make_xlsx
from frappe.utils.file_manager import save_file
from datetime import date
import json
import io

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

        if not data:
            return {
                "message": f"No data found for report from {from_date} to {to_date}.",
                "file_url": ""
            }

        # Convert date fields to string
        safe_columns = convert_dates(columns)
        safe_data = convert_dates(data)

        # Log debug info
        frappe.log_error(
            title="Debug Sales Order Excel Report",
            message=json.dumps({
                "columns": safe_columns,
                "data_sample": safe_data[:5],
                "fieldnames": [col.get("fieldname") for col in safe_columns],
                "labels": [col.get("label") for col in safe_columns]
            }, default=str)
        )

        # Build rows
        header = [col.get("label") or col.get("fieldname") or "Unnamed" for col in safe_columns]
        rows = [header]

        for row in safe_data:
            row_values = []
            for col in safe_columns:
                fieldname = col.get("fieldname")
                row_values.append(row.get(fieldname) if fieldname else None)
            rows.append(row_values)

        # Create Excel
        xlsx_file = make_xlsx(rows, report_name)
        file_name = "Sales_Order_Analysis.xlsx"
        file_content = xlsx_file.getvalue()

        # Save file
        saved_file = save_file(
            file_name,
            file_content,
            "User",
            frappe.session.user,
            is_private=0
        )

        return {
            "file_url": saved_file.file_url,
            "message": f"Excel report generated successfully from {from_date} to {to_date}"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Order Report Error")
        return {"error": str(e)}
