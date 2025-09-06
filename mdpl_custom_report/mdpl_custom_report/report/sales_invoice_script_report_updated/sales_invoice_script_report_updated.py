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
            selected_item_groups += ['11', '12', '13', '14', '14 Plus', '14 Pro', '14 Pro Max', '15', '15 Plus', '15 Pro', '15 Pro Max','16' , '16 Plus' , '16 Pro' , '16 Pro Max']
        if 'iPad' in filters['parent_item_group']:
            selected_item_groups += ['iPad Air 6th gen', 'iPad Pro 5th gen', 'Ipad 9th gen', 'iPad 10th gen', 'Ipad Air 5th gen', 'Ipad pro 4th gen', 'iPad Pro 3rd Gen']
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

    # Sanitize dynamic column names (replace spaces with underscores, lowercase)
    sanitized_groups = [group.replace(' ', '_').lower() for group in selected_item_groups]

    # Create the dynamic SELECT clause based on selected item groups
    group_select_clause = ", ".join(
        f"SUM(CASE WHEN ig.item_group_name = %s THEN si_item.qty ELSE 0 END) AS `{sanitized_group}`"
        for sanitized_group in sanitized_groups
    )

    # Base query and params
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
    """

    params = selected_item_groups[:]  # for group_select_clause placeholders

    # Join Customer Mapping table if sales_person filter is applied
    if filters.get('sales_person'):
        query += """
        INNER JOIN `tabCustomer Mapping` cm ON si.customer = cm.customer
        """

    # Construct WHERE clause
    where_clauses = [
        "si.docstatus = 1",
        "si.is_return = 0",
        "si.posting_date BETWEEN %s AND %s"
    ]
    params.extend([filters['from_date'], filters['to_date']])

    # itm_group filter (only if itm_group is selected)
    if filters.get('itm_group'):
        placeholders = ', '.join(['%s'] * len(filters['itm_group']))
        where_clauses.append(f"ig.item_group_name IN ({placeholders})")
        params.extend(filters['itm_group'])

    # parent_item_group filter (only if itm_group is NOT selected)
    if filters.get('parent_item_group') and not filters.get('itm_group'):
        placeholders = ', '.join(['%s'] * len(filters['parent_item_group']))
        where_clauses.append(f"ig.parent_item_group IN ({placeholders})")
        params.extend(filters['parent_item_group'])

    # customer filter
    if filters.get('customer'):
        placeholders = ', '.join(['%s'] * len(filters['customer']))
        where_clauses.append(f"si.customer IN ({placeholders})")
        params.extend(filters['customer'])

    # apple_id filter
    if filters.get('apple_id'):
        where_clauses.append("c.apple_id IS NOT NULL AND c.apple_id != ''")

    # sales_person filter (via Customer Mapping)
    if filters.get('sales_person'):
        where_clauses.append("cm.parent = %s")
        params.append(filters['sales_person'])

    # Combine WHERE clauses
    query += " WHERE " + " AND ".join(where_clauses)

    query += """
    GROUP BY 
        si.customer
    ORDER BY 
        si.customer
    """

    # Log for debugging
    frappe.logger().info(f"Executing query: {query}")
    frappe.logger().info(f"With params: {params}")

    try:
        data = frappe.db.sql(query, params, as_dict=True)
    except Exception as e:
        frappe.logger().error(f"Error executing query: {e}")
        raise

    # Add missing customers with zero values based on filters
    # (Your previous logic for filling missing customers is preserved here)

    # Function to add missing customers
    def add_missing_customers(customers_query, customers_params):
        all_customers = frappe.db.sql(customers_query, customers_params, as_dict=True)
        existing_customers = {row['customer'] for row in data}
        for cust in all_customers:
            if cust['customer'] not in existing_customers:
                data.append({ "customer": cust['customer'], **{sg: 0 for sg in sanitized_groups} })

    # Conditions when to add all customers with zero values
    # You can adjust these as needed to fit your original logic

    if (filters.get("itm_group") and not filters.get("apple_id") and not filters.get('customer')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer`", [])

    if (filters.get("itm_group") and filters.get("apple_id") and not filters.get('customer')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer` WHERE apple_id > 1", [])

    if (not filters.get("itm_group") and filters.get("apple_id") and not filters.get('customer') and not filters.get('parent_item_group')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer` WHERE apple_id > 1", [])

    if (not filters.get("itm_group") and not filters.get("apple_id") and not filters.get('customer') and not filters.get('parent_item_group')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer`", [])

    if (not filters.get("itm_group") and not filters.get("apple_id") and not filters.get('customer') and filters.get('parent_item_group')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer`", [])

    if (not filters.get("itm_group") and filters.get("apple_id") and not filters.get('customer') and filters.get('parent_item_group')):
        add_missing_customers("SELECT name AS customer FROM `tabCustomer` WHERE apple_id > 1", [])

    # If no data is returned at all, return all customers with zero values
    if not data:
        customer_query = "SELECT name AS customer FROM `tabCustomer` WHERE disabled = 0"
        cust_params = []
        if filters.get('customer'):
            placeholders = ', '.join(['%s'] * len(filters['customer']))
            customer_query += f" AND name IN ({placeholders})"
            cust_params.extend(filters['customer'])

        all_customers = frappe.db.sql(customer_query, cust_params, as_dict=True)
        data = [{
            "customer": cust['customer'],
            **{sg: 0 for sg in sanitized_groups}
        } for cust in all_customers]

    # Dynamically add columns for each selected item group
    columns.extend({
        "label": group,
        "fieldname": sanitized_group,
        "fieldtype": "Float",
        "width": 120
    } for group, sanitized_group in zip(selected_item_groups, sanitized_groups))

    # Add total column for sum of all item groups
    columns.append({
        "label": "Total",
        "fieldname": "total",
        "fieldtype": "Float",
        "width": 150
    })

    # Calculate the total column for each row
    for row in data:
        row['total'] = sum(row.get(sg, 0) for sg in sanitized_groups)

    return columns, data
