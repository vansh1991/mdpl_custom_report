import frappe
from datetime import timedelta


def execute(filters=None):
    filters = filters or {}

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.msgprint("Please select both From Date and To Date.")
        return [], []

    # ---- Get all Item Groups ----
    all_item_groups = frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group"],
        filters={"is_group": 0},
        order_by="name",
    )

    selected_item_groups = []

    # Parent Item Group Filter
    if filters.get("parent_item_group"):
        parent_groups = filters["parent_item_group"]
        selected_item_groups = [
            ig.name for ig in all_item_groups if ig.parent_item_group in parent_groups
        ]

    # Direct Item Group Filter
    if filters.get("itm_group"):
        selected_item_groups = filters["itm_group"]

    # If nothing selected, include all leaf groups
    if not selected_item_groups:
        selected_item_groups = [ig.name for ig in all_item_groups]

    # ---- Prepare Week Ranges ----
    from_date = frappe.utils.getdate(filters["from_date"])
    to_date = frappe.utils.getdate(filters["to_date"])

    def get_sunday_start(date):
        # Adjust to nearest previous Sunday
        return date - timedelta(days=date.weekday() + 1) if date.weekday() != 6 else date

    week_ranges = []
    current_start = get_sunday_start(from_date)
    while current_start <= to_date:
        week_end = current_start + timedelta(days=6)
        week_ranges.append((current_start, min(week_end, to_date)))
        current_start = week_end + timedelta(days=1)

    # ---- Build Columns ----
    columns = [{"label": "Sales Rep", "fieldname": "sales_rep", "fieldtype": "Data", "width": 150}]
    sanitized_groups = [g.replace(" ", "_").lower() for g in selected_item_groups]

    for idx, (start, end) in enumerate(week_ranges, 1):
        for group, s_group in zip(selected_item_groups, sanitized_groups):
            columns.append({
                "label": f"{group} - Week {idx} ({start.strftime('%d-%b')} to {end.strftime('%d-%b')})",
                "fieldname": f"{s_group}_week{idx}",
                "fieldtype": "Float",
                "width": 140
            })
        columns.append({
            "label": f"Total - Week {idx}",
            "fieldname": f"total_week{idx}",
            "fieldtype": "Float",
            "width": 130
        })

    columns.append({"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Float", "width": 150})

    # ---- Build Sales Rep List ----
    all_sales_reps = frappe.get_all("Sales Rep Info", fields=["sales_rep"])
    selected_sales_reps = [rep.sales_rep for rep in all_sales_reps]

    if filters.get("sales_rep"):
        selected_sales_reps = [filters["sales_rep"]]

    # ---- Data Calculation ----
    data = []

    for sales_rep in selected_sales_reps:
        row = {"sales_rep": sales_rep}
        grand_total = 0

        for idx, (start, end) in enumerate(week_ranges, 1):
            week_total = 0

            for group, s_group in zip(selected_item_groups, sanitized_groups):
                query = f"""
                    SELECT SUM(si_item.qty) AS qty
                    FROM `tabSales Invoice` si
                    INNER JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
                    INNER JOIN `tabItem` i ON si_item.item_code = i.name
                    INNER JOIN `tabItem Group` ig ON i.item_group = ig.name
                    INNER JOIN `tabCustomer` c ON si.customer = c.name
                    WHERE si.docstatus = 1
                        AND si.is_return = 0
                        AND si.posting_date BETWEEN %s AND %s
                        AND ig.name = %s
                        AND si.customer IN (
                            SELECT a.Customer
                            FROM `tabCustomer Mapping` a
                            JOIN `tabSales Rep Info` b ON a.parent = b.name
                            WHERE b.sales_rep = %s
                        )
                """

                params = [start, end, group, sales_rep]

                # Apple ID filter
                if "apple_id" in filters:
                    if filters["apple_id"] == 1:
                        query += " AND c.apple_id IS NOT NULL AND c.apple_id != ''"
                    elif filters["apple_id"] == 0:
                        query += " AND (c.apple_id IS NULL OR c.apple_id = '')"

                qty = frappe.db.sql(query, params, as_dict=True)[0].qty or 0
                row[f"{s_group}_week{idx}"] = qty
                week_total += qty
                grand_total += qty

            row[f"total_week{idx}"] = week_total

        row["grand_total"] = grand_total
        data.append(row)

    return columns, data
