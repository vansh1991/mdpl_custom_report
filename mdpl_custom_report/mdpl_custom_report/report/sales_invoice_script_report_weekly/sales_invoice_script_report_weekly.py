import frappe
from datetime import timedelta

def execute(filters=None):
    filters = filters or {}

    # ---- Validate dates ----
    if not filters.get("from_date") or not filters.get("to_date"):
        # Instead of msgprint popup, just return empty
        return [], []

    # ---- Get all leaf item groups ----
    all_item_groups = frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group"],
        filters={"is_group": 0},
        order_by="name"
    )

    # ---- Apply item group filters ----
    if filters.get("itm_group"):
        selected_item_groups = filters["itm_group"]
    elif filters.get("parent_item_group"):
        selected_item_groups = [
            ig.name for ig in all_item_groups
            if ig.parent_item_group in filters["parent_item_group"]
        ]
    else:
        selected_item_groups = [ig.name for ig in all_item_groups]

    sanitized_groups = [g.replace(" ", "_").lower() for g in selected_item_groups]

    # ---- Week calculation ----
    from_date = frappe.utils.getdate(filters["from_date"])
    to_date = frappe.utils.getdate(filters["to_date"])

    def get_week_ranges(start, end):
        weeks = []
        current_start = start
        while current_start <= end:
            week_end = current_start + timedelta(days=(6 - current_start.weekday()))
            if week_end > end:
                week_end = end
            weeks.append((current_start, week_end))
            current_start = week_end + timedelta(days=1)
        return weeks

    week_ranges = get_week_ranges(from_date, to_date)

    # ---- Columns ----
    columns = [{"label": "Customer", "fieldname": "customer", "fieldtype": "Data", "width": 180}]
    for i, (week_start, week_end) in enumerate(week_ranges, start=1):
        week_label = f"Week {i} ({week_start.strftime('%d-%b')} to {week_end.strftime('%d-%b')})"
        for group, sg in zip(selected_item_groups, sanitized_groups):
            columns.append({
                "label": f"{group} - {week_label}",
                "fieldname": f"{sg}_week{i}",
                "fieldtype": "Float",
                "width": 120
            })
        columns.append({
            "label": f"Total {week_label}",
            "fieldname": f"total_week{i}",
            "fieldtype": "Float",
            "width": 120
        })
    columns.append({"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Float", "width": 150})

    # ---- Apple ID Filter ----
    apple_id_sql = ""
    apple_id_val = filters.get("apple_id")
    if apple_id_val in (1, "1", True, "true", "True"):
        apple_id_sql = " AND (c.apple_id IS NOT NULL AND c.apple_id != '')"
    elif apple_id_val in (0, "0", "", None, False, "false", "False"):
        apple_id_sql = " AND (c.apple_id IS NULL OR c.apple_id = '')"

    # ---- Sales Rep Filter ----
    sales_rep_filter_sql = ""
    sales_rep_params = []
    if filters.get("sales_rep"):
        sales_rep_filter_sql = """
            AND si.customer IN (
                SELECT cm.customer
                FROM `tabCustomer Mapping` cm
                INNER JOIN `tabSales Rep Info` sri ON cm.parent = sri.name
                WHERE sri.sales_rep = %s
            )
        """
        sales_rep_params = [filters["sales_rep"]]

    # ---- Customer Filter (Multi-Select) ----
    customer_filter_sql = ""
    customer_filter_params = []
    if filters.get("customer"):
        customer_list = filters["customer"]  # MultiSelect returns a list
        if customer_list:
            placeholders = ", ".join(["%s"] * len(customer_list))
            customer_filter_sql = f" AND si.customer IN ({placeholders})"
            customer_filter_params = customer_list

    # ---- Fetch Customers ----
    customer_query = f"""
        SELECT name FROM `tabCustomer` c
        WHERE c.disabled = 0
        {apple_id_sql}
    """
    customer_params = []

    if filters.get("sales_rep"):
        customer_query += """
            AND c.name IN (
                SELECT cm.customer
                FROM `tabCustomer Mapping` cm
                INNER JOIN `tabSales Rep Info` sri ON cm.parent = sri.name
                WHERE sri.sales_rep = %s
            )
        """
        customer_params += sales_rep_params

    if filters.get("customer"):
        customer_query += f" AND c.name IN ({', '.join(['%s']*len(filters['customer']))})"
        customer_params += filters["customer"]

    all_customers = frappe.db.sql(customer_query, customer_params, as_dict=True)

    # Initialize customer dictionary with zero values
    customer_dict = {
        c.name: {col["fieldname"]: 0 for col in columns if col["fieldname"] != "customer"}
        for c in all_customers
    }

    # ---- Weekly Sales Query ----
    for i, (week_start, week_end) in enumerate(week_ranges, start=1):
        for group, sg in zip(selected_item_groups, sanitized_groups):
            query = f"""
                SELECT si.customer, item.item_group, SUM(si_item.qty) AS qty
                FROM `tabDelivery Note` si
                INNER JOIN `tabDelivery Note Item` si_item ON si.name = si_item.parent
                INNER JOIN `tabItem` item ON si_item.item_code = item.name
                INNER JOIN `tabItem Group` ig ON item.item_group = ig.name
                INNER JOIN `tabCustomer` c ON si.customer = c.name
                WHERE si.docstatus = 1
                  AND si.is_return = 0
                  AND si.posting_date BETWEEN %s AND %s
                  AND ig.name = %s
                  {apple_id_sql}
                  {sales_rep_filter_sql}
                  {customer_filter_sql}
                GROUP BY si.customer, item.item_group
            """
            query_params = [week_start, week_end, group] + sales_rep_params + customer_filter_params
            rows = frappe.db.sql(query, query_params, as_dict=True)
            for r in rows:
                cust = r.customer
                qty = r.qty or 0
                fieldname = f"{sg}_week{i}"
                if cust in customer_dict:
                    customer_dict[cust][fieldname] += qty

    # ---- Calculate Totals ----
    for cust in customer_dict:
        grand_total = 0
        for i in range(1, len(week_ranges) + 1):
            week_total = sum(customer_dict[cust].get(f"{sg}_week{i}", 0) for sg in sanitized_groups)
            customer_dict[cust][f"total_week{i}"] = week_total
            grand_total += week_total
        customer_dict[cust]["grand_total"] = grand_total

    # ---- Prepare Final Data ----
    data = []
    for c in all_customers:
        row = {"customer": c.name}
        row.update(customer_dict[c.name])
        data.append(row)

    return columns, data
