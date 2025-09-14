import frappe

def execute(filters=None):
    filters = filters or {}

    # Ensure both dates are selected
    if not filters.get('from_date') or not filters.get('to_date'):
        frappe.msgprint("Please select both From Date and To Date.")
        return [], []

    # Define all static item groups
    all_item_groups = [
        'Airpod 2', 'Airpod 3', 'Airpod Pro', 'Airpod Pro2',
        '11', '12', '13', '14', '14 Plus', '14 Pro', '14 Pro Max',
        '15', '15 Plus', '15 Pro', '15 Pro Max', 'iPad Air 6th gen',
        'iPad Pro 5th gen', 'Ipad 9th gen', 'iPad 10th gen',
        'Ipad Air 5th gen', 'Ipad pro 4th gen', 'iPad Pro 3rd Gen', '(Accessories)',
        'Watch SE 2', 'Watch 8', 'WATCH Ultra', 'Watch 9', 'WATCH Ultra 2',
        'Mac Air M2', 'Mac Air M3','16' , '16 Plus' , '16 Pro' , '16 Pro Max','AirPod 4','Series 10'
    ]

    # Initialize selected_item_groups
    selected_item_groups = []

    # Apply parent_item_group logic first
    if filters.get('parent_item_group'):
        if 'Macbook' in filters['parent_item_group']:
            selected_item_groups += ['Mac Air M2', 'Mac Air M3']
        if 'AirPods' in filters['parent_item_group']:
            selected_item_groups += ['Airpod 2', 'Airpod 3', 'Airpod Pro', 'Airpod Pro2','AirPod 4']
        if 'iPhone' in filters['parent_item_group']:
            selected_item_groups += ['11', '12', '13', '14', '14 Plus', '14 Pro', '14 Pro Max', 
                                     '15', '15 Plus', '15 Pro', '15 Pro Max','16' , '16 Plus' , '16 Pro' , '16 Pro Max']
        if 'iPad' in filters['parent_item_group']:
            selected_item_groups += ['iPad Air 6th gen', 'iPad Pro 5th gen', 'Ipad 9th gen', 'iPad 10th gen', 
                                     'Ipad Air 5th gen', 'Ipad pro 4th gen', 'iPad Pro 3rd Gen']
        if 'Accessories' in filters['parent_item_group']:
            selected_item_groups += ['(Accessories)']
        if 'Apple Watch' in filters['parent_item_group']:
            selected_item_groups += ['Watch SE 2', 'Watch 8', 'WATCH Ultra', 'Watch 9', 'WATCH Ultra 2','Series 10']
        
    # If itm_group is selected, prioritize itm_group over parent_item_group
    if filters.get('itm_group'):
        selected_item_groups = filters['itm_group']

    # If no filters are applied, show all item groups
    if not selected_item_groups:
        selected_item_groups = all_item_groups

    # Create column definitions, starting with the customer column
    columns = [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Data", "width": 150}
    ]

    # Sanitize dynamic column names (replace spaces with underscores)
    sanitized_groups = [group.replace(' ', '_').lower() for group in selected_item_groups]

    # Create the dynamic SELECT clause
    group_select_clause = ", ".join(
        f"SUM(CASE WHEN ig.item_group_name = '{group}' THEN si_item.qty ELSE 0 END) AS `{sanitized_group}`"
        for group, sanitized_group in zip(selected_item_groups, sanitized_groups)
    )

    # Add Sales Rep filter via customer mapping join
    sales_rep_filter = ""
    sales_rep_params = []
    if filters.get('sales_rep'):
        sales_rep_filter = """
        AND si.customer IN (
            SELECT a.Customer
            FROM `tabCustomer Mapping` a
            JOIN `tabSales Rep Info` b ON a.parent = b.name
            WHERE b.sales_rep = %s
        )
        """
        sales_rep_params.append(filters['sales_rep'])

    # Construct the base query with filters
    where_clause = (
        "si.docstatus = 1 "
        "AND si.is_return = 0 "
        "AND si.posting_date BETWEEN %s AND %s"
    )

    # itm_group filter
    if filters.get('itm_group'):
        group_placeholders = ', '.join(['%s'] * len(filters['itm_group']))
        where_clause += f" AND ig.item_group_name IN ({group_placeholders})"

    # parent_item_group filter
    if filters.get('parent_item_group') and not filters.get('itm_group'):
        parent_group_placeholders = ', '.join(['%s'] * len(filters['parent_item_group']))
        where_clause += f" AND ig.parent_item_group IN ({parent_group_placeholders})"

    # customer filter
    if filters.get('customer'):
        customer_placeholders = ', '.join(['%s'] * len(filters['customer']))
        where_clause += f" AND si.customer IN ({customer_placeholders})"

    # Apple ID filter
    if "apple_id" in filters:
        if filters["apple_id"] == 1:   # checked
            where_clause += " AND c.apple_id IS NOT NULL AND c.apple_id != ''"
        elif filters["apple_id"] == 0: # unchecked
            where_clause += " AND (c.apple_id IS NULL OR c.apple_id = '')"

    # Append sales_rep filter
    if filters.get('sales_rep'):
        where_clause += sales_rep_filter

    # Construct the final query
    query = f"""
    SELECT 
        si.customer AS customer,
        {group_select_clause}
    FROM 
        `tabSales Invoice` si
    INNER JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
    INNER JOIN `tabItem` item ON si_item.item_code = item.name
    INNER JOIN `tabItem Group` ig ON item.item_group = ig.name
    INNER JOIN `tabCustomer` c ON si.customer = c.name
    WHERE  
        {where_clause}
    GROUP BY 
        si.customer
    ORDER BY 
        si.customer;
    """

    # Build params
    params = [filters.get('from_date'), filters.get('to_date')]
    if filters.get('itm_group'):
        params.extend(filters['itm_group'])
    if filters.get('parent_item_group') and not filters.get('itm_group'):
        params.extend(filters['parent_item_group'])
    if filters.get('customer'):
        params.extend(filters['customer'])
    if filters.get('sales_rep'):
        params.extend(sales_rep_params)

    try:
        data = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.throw(f"Error executing query: {e}")

    # ---- Handle missing customers (zero sales) ----
    def add_missing_customers(data):
        all_customer_query = "SELECT name AS customer FROM `tabCustomer` WHERE disabled = 0"
        params = []

        # Apply Apple ID filter
        if "apple_id" in filters:
            if filters["apple_id"] == 1:
                all_customer_query += " AND apple_id IS NOT NULL AND apple_id != ''"
            elif filters["apple_id"] == 0:
                all_customer_query += " AND (apple_id IS NULL OR apple_id = '')"

        # Apply Sales Rep filter
        if filters.get("sales_rep"):
            all_customer_query += """
                AND name IN (
                    SELECT a.Customer
                    FROM `tabCustomer Mapping` a
                    JOIN `tabSales Rep Info` b ON a.parent = b.name
                    WHERE b.sales_rep = %s
                )
            """
            params.append(filters["sales_rep"])

        # Apply Customer filter
        if filters.get("customer"):
            placeholders = ', '.join(['%s'] * len(filters['customer']))
            all_customer_query += f" AND name IN ({placeholders})"
            params.extend(filters['customer'])

        all_customers = frappe.db.sql(all_customer_query, params, as_dict=True)
        existing_customers = {row['customer'] for row in data}

        for customer_row in all_customers:
            if customer_row.get("customer") not in existing_customers:
                data.append({
                    "customer": customer_row.get("customer"),
                    **{sg: 0 for sg in sanitized_groups}
                })

    add_missing_customers(data)

    # ---- Columns ----
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
