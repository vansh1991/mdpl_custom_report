import frappe

def execute(filters=None):
    filters = filters or {}

    # Ensure both dates are selected
    if not filters.get('from_date') or not filters.get('to_date'):
        frappe.msgprint("Please select both From Date and To Date.")
        return [], []

    # Dynamically fetch all Item Groups
    all_item_groups = frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group"],
        filters={"is_group": 0},  # only leaf groups
        order_by="name"
    )

    selected_item_groups = []

    # If parent_item_group filter is given
    if filters.get('parent_item_group'):
        parent_groups = filters['parent_item_group']
        selected_item_groups = [
            ig.name for ig in all_item_groups if ig.parent_item_group in parent_groups
        ]

    # If itm_group is selected, prioritize itm_group over parent_item_group
    if filters.get('itm_group'):
        selected_item_groups = filters['itm_group']

    # If no filters are applied, show all item groups
    if not selected_item_groups:
        selected_item_groups = [d["name"] for d in all_item_groups]

    # Sanitize dynamic column names
    sanitized_groups = [group.replace(' ', '_').lower() for group in selected_item_groups]

    # Dynamic SELECT for item groups
    group_select_clause = ", ".join(
        f"SUM(CASE WHEN ig.name = '{group}' THEN si_item.qty ELSE 0 END) AS `{sanitized_group}`"
        for group, sanitized_group in zip(selected_item_groups, sanitized_groups)
    )

    # Base where clause
    where_clause = (
        "si.docstatus = 1 AND si.is_return = 0 "
        "AND si.posting_date BETWEEN %s AND %s"
    )

    # Optional filters
    if filters.get('itm_group'):
        placeholders = ', '.join(['%s'] * len(filters['itm_group']))
        where_clause += f" AND ig.name IN ({placeholders})"
    elif filters.get('parent_item_group'):
        placeholders = ', '.join(['%s'] * len(filters['parent_item_group']))
        where_clause += f" AND ig.parent_item_group IN ({placeholders})"

    if filters.get('customer'):
        placeholders = ', '.join(['%s'] * len(filters['customer']))
        where_clause += f" AND si.customer IN ({placeholders})"

    # Apple ID filter
    if filters.get("apple_id") in (1, "1", True):
        where_clause += " AND c.apple_id IS NOT NULL AND c.apple_id != ''"
    else:
        where_clause += " AND (c.apple_id IS NULL OR c.apple_id = '')"

    # Sales Rep and Sales Category filters
    sales_rep_filter = ""
    sales_category_filter = ""
    params = [filters.get('from_date'), filters.get('to_date')]
    if filters.get('itm_group'):
        params.extend(filters['itm_group'])
    elif filters.get('parent_item_group'):
        params.extend(filters['parent_item_group'])
    if filters.get('customer'):
        params.extend(filters['customer'])
    if filters.get('sales_rep'):
        sales_rep_filter = " AND b.sales_rep = %s"
        params.append(filters['sales_rep'])
    if filters.get('sales_category'):
        placeholders = ', '.join(['%s'] * len(filters['sales_category']))
        sales_category_filter = f" AND sc.name IN ({placeholders})"
        params.extend(filters['sales_category'])

    # Final query
    query = f"""
    SELECT 
        si.customer AS customer,
        COALESCE(sc.name, 'Unassigned') AS sales_category,
        COALESCE(d.name, 'Unassigned') AS district,
        COALESCE(sd.name, 'Unassigned') AS sub_district,
        COALESCE(MAX(b.sales_rep), 'Unassigned') AS sales_rep_name,
        {group_select_clause}
    FROM `tabDelivery Note` si
    INNER JOIN `tabDelivery Note Item` si_item ON si.name = si_item.parent
    INNER JOIN `tabItem` item ON si_item.item_code = item.name
    INNER JOIN `tabItem Group` ig ON item.item_group = ig.name
    INNER JOIN `tabCustomer` c ON si.customer = c.name
    LEFT JOIN `tabSales Category Customer` scc ON si.customer = scc.customer_name
    LEFT JOIN `tabSales Category` sc ON sc.name = scc.parent
    LEFT JOIN `tabSub District Customer List` sdc ON si.customer = sdc.customer_name
    LEFT JOIN `tabSub District` sd ON sd.name = sdc.parent
    LEFT JOIN `tabDistrict` d ON sd.parent = d.name
    LEFT JOIN `tabCustomer Mapping` cm ON si.customer = cm.customer
    LEFT JOIN `tabSales Rep Info` b ON cm.parent = b.name
    WHERE {where_clause} {sales_rep_filter} {sales_category_filter}
    GROUP BY si.customer, sc.name, sd.name, d.name
    ORDER BY si.customer
    """

    # Execute query
    try:
        data = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.throw(f"Error executing query: {e}")

    # ---- Handle missing customers ----
    def add_missing_customers(data):
        all_customer_query = """
            SELECT c.name AS customer, sc.name AS sales_category, sd.name as sub_district, d.name as district,
                   COALESCE(MAX(b.sales_rep), 'Unassigned') AS sales_rep_name
            FROM `tabCustomer` c
            LEFT JOIN `tabSales Category Customer` scc ON c.name = scc.customer_name
            LEFT JOIN `tabSales Category` sc ON scc.parent = sc.name
            LEFT JOIN `tabSub District Customer List` sdc ON c.name = sdc.customer_name
            LEFT JOIN `tabSub District` sd ON sdc.parent = sd.name
            LEFT JOIN `tabDistrict` d ON sd.parent = d.name
            LEFT JOIN `tabCustomer Mapping` cm ON c.name = cm.customer
            LEFT JOIN `tabSales Rep Info` b ON cm.parent = b.name
            WHERE c.disabled = 0
        """

        params = []
        if filters.get("sales_rep"):
            all_customer_query += " AND b.sales_rep = %s"
            params.append(filters["sales_rep"])
        if filters.get("customer"):
            placeholders = ', '.join(['%s'] * len(filters['customer']))
            all_customer_query += f" AND c.name IN ({placeholders})"
            params.extend(filters['customer'])
        if filters.get("apple_id") in (1, "1", True):
            all_customer_query += " AND c.apple_id IS NOT NULL AND c.apple_id != ''"
        else:
            all_customer_query += " AND (c.apple_id IS NULL OR c.apple_id = '')"

        all_customers = frappe.db.sql(all_customer_query + " GROUP BY c.name, sc.name, sd.name, d.name", params, as_dict=True)
        existing_customers = {(row['customer'], row.get('sales_category')) for row in data}

        for customer_row in all_customers:
            key = (customer_row.get("customer"), customer_row.get("sales_category"))
            if key not in existing_customers:
                data.append({
                    "customer": customer_row.get("customer"),
                    "sales_category": customer_row.get("sales_category") or "Unassigned",
                    "sub_district": customer_row.get("sub_district") or "Unassigned",
                    "district": customer_row.get("district") or "Unassigned",
                    "sales_rep_name": customer_row.get("sales_rep_name") or "Unassigned",
                    **{sg: 0 for sg in sanitized_groups}
                })

    add_missing_customers(data)

    # ---- Columns ----
    columns = [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "District", "fieldname": "district", "fieldtype": "Data", "width": 150},
        {"label": "Sub District", "fieldname": "sub_district", "fieldtype": "Data", "width": 150},
        {"label": "Sales Category", "fieldname": "sales_category", "fieldtype": "Link", "options": "Sales Category", "width": 150},
        {"label": "Sales Rep Name", "fieldname": "sales_rep_name", "fieldtype": "Data", "width": 200},
    ]

    columns.extend({
        "label": group,
        "fieldname": sanitized_group,
        "fieldtype": "Float",
        "width": 120
    } for group, sanitized_group in zip(selected_item_groups, sanitized_groups))

    columns.append({
        "label": "Total",
        "fieldname": "total",
        "fieldtype": "Float",
        "width": 150
    })

    # ---- Totals ----
    for row in data:
        row['total'] = sum(row.get(sg, 0) for sg in sanitized_groups)

    return columns, data
