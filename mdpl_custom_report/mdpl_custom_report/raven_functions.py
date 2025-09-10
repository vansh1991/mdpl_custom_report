import frappe
from frappe.utils import nowdate
from frappe.utils.xlsxutils import make_xlsx
from frappe.utils.file_manager import save_file
from datetime import date
import json

def convert_dates(obj):
    """Recursively convert date objects to ISO string format."""
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
    # Debug incoming parameters
    print(f"Received from_date: {from_date}, to_date: {to_date}")
    print(f"frappe.form_dict: {frappe.form_dict}")
    frappe.logger().debug(f"Received from_date: {from_date}, to_date: {to_date}")
    frappe.logger().debug(f"frappe.form_dict: {frappe.form_dict}")

    # Fallback for arguments passed via frappe.form_dict if function args are None
    if from_date is None:
        from_date = frappe.form_dict.get("from_date")
    if to_date is None:
        to_date = frappe.form_dict.get("to_date")

    # Log after fallback to check final parameters
    frappe.logger().debug(f"After fallback from_date: {from_date}, to_date: {to_date}")
    print(f"After fallback from_date: {from_date}, to_date: {to_date}")

    if not from_date or not to_date:
        print("Error: Both 'from_date' and 'to_date' are required.")
        return {
            "error": "Both 'from_date' and 'to_date' are required."
        }

    report_name = "Sales Order Analysis"
    filters = {"from_date": from_date, "to_date": to_date}

    try:
        print(f"Getting report doc for: {report_name} with filters: {filters}")
        report = frappe.get_doc("Report", report_name)
        columns, data = report.get_data(filters=filters, as_dict=True)

        if not data:
            print(f"No data found for report from {from_date} to {to_date}.")
            return {
                "message": f"No data found for report from {from_date} to {to_date}.",
                "file_url": ""
            }

        # Convert date objects in columns and data
        safe_columns = convert_dates(columns)
        safe_data = convert_dates(data)

        # Log debug info (optional)
        frappe.log_error(
            title="Debug Sales Order Excel Report",
            message=json.dumps({
                "columns": safe_columns,
                "data_sample": safe_data[:5],
                "fieldnames": [col.get("fieldname") for col in safe_columns],
                "labels": [col.get("label") for col in safe_columns]
            }, default=str)
        )

        # Prepare Excel rows
        header = [col.get("label") or col.get("fieldname") or "Unnamed" for col in safe_columns]
        rows = [header]

        for row in safe_data:
            row_values = []
            for col in safe_columns:
                fieldname = col.get("fieldname")
                value = row.get(fieldname) if fieldname else ""
                if isinstance(value, date):
                    value = value.isoformat()
                elif value is None:
                    value = ""
                row_values.append(value)
            rows.append(row_values)

        # Create Excel file
        xlsx_file = make_xlsx(rows, report_name)
        file_name = f"Sales_Order_Analysis_{from_date}_to_{to_date}.xlsx"
        file_content = xlsx_file.getvalue()

        # Save file to public location
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
