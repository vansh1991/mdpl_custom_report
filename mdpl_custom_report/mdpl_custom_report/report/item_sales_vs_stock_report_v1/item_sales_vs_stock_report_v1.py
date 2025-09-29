import frappe
from frappe.utils.nestedset import get_descendants_of

def execute(filters=None):
    if not filters:
        filters = {}

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw("Please select From Date and To Date")

    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
        {"label": "Parent Item Group", "fieldname": "parent_item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": "On Hand Qty", "fieldname": "on_hand_qty", "fieldtype": "Float", "width": 120},
        {"label": "Sold Qty", "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
        {"label": "Custom Qty (Ratio)", "fieldname": "custom_qty", "fieldtype": "Float", "width": 130},
    ]


def get_data(filters):
    values = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "apple_id_flag": 1 if filters.get("apple_id") else 0
    }

    conditions = "1=1"
    having_clauses = []

    # Exclude zero On Hand if not checked
    if not filters.get("include_zero_on_hand"):
        having_clauses.append("on_hand_qty > 0")

    # Exclude zero Sold Qty if not checked
    if not filters.get("include_zero_sold_qty"):
        having_clauses.append("sold_qty > 0")

    having_condition = ""
    if having_clauses:
        having_condition = "HAVING " + " AND ".join(having_clauses)
  
    # Parent Item Group
    if filters.get("parent_item_group"):
        parent_group = filters["parent_item_group"].strip("()")
        child_groups = get_descendants_of("Item Group", parent_group)
        child_groups.append(parent_group)
        conditions += " AND item.item_group IN %(child_groups)s"
        values["child_groups"] = tuple(child_groups)

    # Item Group
    if filters.get("item_group"):
        conditions += " AND item.item_group IN %(item_groups)s"
        values["item_groups"] = tuple(filters.get("item_group"))

    # Warehouse
    if filters.get("warehouse"):
        conditions += " AND bin.warehouse = %(warehouse)s"

    # Apple ID filter
    apple_flag = values["apple_id_flag"]
    if apple_flag == 1:
        on_hand_expr = "SUM(DISTINCT IF(c.apple_id IS NOT NULL, IFNULL(bin.actual_qty, 0), 0))"
        sold_expr = "SUM(IF(c.apple_id IS NOT NULL AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s, si_item.qty, 0))"
    else:
        on_hand_expr = "SUM(DISTINCT IFNULL(bin.actual_qty, 0))"
        sold_expr = "SUM(IF(si.posting_date BETWEEN %(from_date)s AND %(to_date)s, si_item.qty, 0))"

    sql = f"""
        SELECT 
            item.item_code,
            item.item_name,
            item.item_group,
            ig.parent_item_group,
            bin.warehouse,
            {on_hand_expr} AS on_hand_qty,
            {sold_expr} AS sold_qty,
            ROUND({on_hand_expr} / NULLIF({sold_expr}, 0), 2) AS custom_qty
        FROM tabItem item
        LEFT JOIN tabBin bin ON bin.item_code = item.item_code
        LEFT JOIN `tabSales Invoice Item` si_item ON si_item.item_code = item.item_code
        LEFT JOIN `tabSales Invoice` si ON si.name = si_item.parent AND si.docstatus = 1
        JOIN `tabCustomer` c ON c.name = si.customer
        LEFT JOIN `tabItem Group` ig ON ig.name = item.item_group
        WHERE 
        {conditions} //
        GROUP BY 
            item.item_code, item.item_name, item.item_group, ig.parent_item_group, bin.warehouse
        {having_condition}
        ORDER BY on_hand_qty DESC
    """

    return frappe.db.sql(sql, values, as_dict=True)
