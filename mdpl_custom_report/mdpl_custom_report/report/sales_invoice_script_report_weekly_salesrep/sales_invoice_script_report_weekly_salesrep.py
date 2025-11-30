import frappe
from frappe import _
from frappe.utils import getdate, add_days

def execute(filters=None):
    filters = filters or {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not from_date or not to_date:
        frappe.throw(_("Please select both From Date and To Date"))

    item_group = filters.get("item_group")
    parent_item_group = filters.get("parent_item_group")
    sales_rep = filters.get("sales_rep")

    # Get week ranges from Monday to Sunday
    week_ranges = get_week_ranges(from_date, to_date)

    # Prepare columns
    columns = [
        {"label": _("Sales Rep"), "fieldname": "sales_rep", "fieldtype": "Link", "options": "Sales Person", "width": 150},
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Data", "width": 150},
    ]

    for idx, (week_start, week_end) in enumerate(week_ranges, 1):
        columns.append({
            "label": _("Week {0} Amount ({1} to {2})").format(idx, week_start, week_end),
            "fieldname": f"week_{idx}_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        })
        columns.append({
            "label": _("Week {0} Qty ({1} to {2})").format(idx, week_start, week_end),
            "fieldname": f"week_{idx}_qty",
            "fieldtype": "Float",
            "width": 100
        })

    # Build SQL query
    query = """
        SELECT 
            sr.sales_rep, 
            i.item_group, 
            si.posting_date, 
            si_item.amount,
            si_item.qty
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
        JOIN `tabItem` i ON si_item.item_code = i.name
        JOIN `tabCustomer Mapping` cm ON si.customer = cm.customer
        JOIN `tabSales Rep Info` sr ON cm.parent = sr.name
        WHERE si.docstatus = 1
          AND si.posting_date BETWEEN %s AND %s
    """

    params = [from_date, to_date]

    if item_group:
        query += " AND i.item_group = %s"
        params.append(item_group)

    if parent_item_group:
        query += " AND i.parent_item_group = %s"
        params.append(parent_item_group)

    if sales_rep:
        query += " AND sr.sales_rep = %s"
        params.append(sales_rep)

    sales_data = frappe.db.sql(query, params, as_dict=True)

    # Aggregate data by Sales Rep + Item Group + Week
    data_dict = {}
    for row in sales_data:
        key = (row.sales_rep, row.item_group)
        if key not in data_dict:
            data_dict[key] = {"sales_rep": row.sales_rep, "item_group": row.item_group}
            for idx in range(len(week_ranges)):
                data_dict[key][f"week_{idx+1}_amount"] = 0.0
                data_dict[key][f"week_{idx+1}_qty"] = 0.0

        posting_date = getdate(row.posting_date)
        for idx, (week_start, week_end) in enumerate(week_ranges, 1):
            if week_start <= posting_date <= week_end:
                data_dict[key][f"week_{idx}_amount"] += row.amount
                data_dict[key][f"week_{idx}_qty"] += row.qty
                break

    data = list(data_dict.values())
    return columns, data


def get_week_ranges(from_date, to_date):
    from_date = getdate(from_date)
    to_date = getdate(to_date)

    # Move from_date to Monday
    weekday = from_date.weekday()  # Mon=0 … Sun=6
    if weekday != 0:
        from_date = add_days(from_date, -weekday)

    weeks = []
    start = from_date

    while start <= to_date:
        end = add_days(start, 6)
        if end > to_date:
            end = to_date
        weeks.append((start, end))
        start = add_days(start, 7)

    return weeks
