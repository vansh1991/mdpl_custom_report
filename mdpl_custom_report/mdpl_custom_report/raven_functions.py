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

        safe_columns = convert_dates(columns)
        safe_data = convert_dates(data)

        # Convert column dicts to list of labels (header row)
        header = [col.get("label") for col in safe_columns]
        rows = [header] + [[row.get(col.get("fieldname")) for col in safe_columns] for row in safe_data]

        xlsx_file = make_xlsx(rows, report_name)

        # Save the file to public/files
        file_name = f"{report_name.replace(' ', '_')}_{from_date}_to_{to_date}.xlsx"
        saved_file = save_file(file_name, io.BytesIO(xlsx_file.getvalue()), "Report", None, is_private=0)

        return {
            "file_url": saved_file.file_url,
            "message": f"Excel report generated successfully from {from_date} to {to_date}"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Order Report Error")
        return {"error": str(e)}