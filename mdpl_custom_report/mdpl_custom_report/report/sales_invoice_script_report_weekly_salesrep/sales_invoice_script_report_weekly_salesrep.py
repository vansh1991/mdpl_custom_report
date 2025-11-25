from frappe import _

def execute(filters=None):
    filters = filters or {}

    # Required filters
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    if not from_date or not to_date:
        frappe.throw(_("Please select both From Date and To Date"))

    # Item Group filter
    item_group = filters.get("item_group")
    parent_item_group = filters.get("parent_item_group")

    # Sales Rep filter
    sales_rep_filter = filters.get("sales_rep")

    # Now you can use these filters in your SQL queries
    # Example:
    query = """
        SELECT SUM(si_item.qty) AS qty
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
        INNER JOIN `tabItem` i ON si_item.item_code = i.name
        INNER JOIN `tabItem Group` ig ON i.item_group = ig.name
        WHERE si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
    """

    params = [from_date, to_date]

    if item_group:
        query += " AND ig.name = %s"
        params.append(item_group)

    if parent_item_group:
        query += " AND ig.parent_item_group = %s"
        params.append(parent_item_group)

    if sales_rep_filter:
        query += """
            AND si.customer IN (
                SELECT a.customer
                FROM `tabCustomer Mapping` a
                JOIN `tabSales Rep Info` b ON a.parent = b.name
                WHERE b.sales_rep = %s
            )
        """
        params.append(sales_rep_filter)

    data = frappe.db.sql(query, params, as_dict=True)
    return [], data
