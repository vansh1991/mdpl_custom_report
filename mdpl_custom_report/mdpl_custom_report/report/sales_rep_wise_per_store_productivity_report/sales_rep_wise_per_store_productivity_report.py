import frappe
from frappe import _


class SalesRepProductivityReport:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.from_date = self.filters.get("from_date")
        self.to_date = self.filters.get("to_date")
        self.item_group = self.filters.get("item_group")
        self.parent_item_group = self.filters.get("parent_item_group")
        self.sales_rep = self.filters.get("sales_rep")

    def run(self):
        self.validate_filters()
        data = self.calculate_productivity()
        columns = self.get_columns()
        return columns, data

    def validate_filters(self):
        if not self.from_date or not self.to_date:
            frappe.throw(_("From Date and To Date are required."))

    def calculate_productivity(self):
        sales_reps = self.get_sales_rep_list()

        results = []

        for rep in sales_reps:
            total_units = self.get_total_units(rep)
            total_stores = self.get_total_stores(rep)

            productivity = (total_units / total_stores) if total_stores else 0

            results.append({
                "sales_rep": rep,
                "total_units": total_units,
                "total_stores": total_stores,
                "productivity": productivity
            })

        return results

    def get_sales_rep_list(self):
        if self.sales_rep:
            return [self.sales_rep]

        reps = frappe.get_all("Sales Rep Info", pluck="sales_rep")
        return reps

    def get_total_units(self, sales_rep):
        conditions = ""
        params = {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "sales_rep": sales_rep
        }

        if self.item_group:
            conditions += " AND ig.name = %(item_group)s"
            params["item_group"] = self.item_group

        if self.parent_item_group:
            conditions += " AND ig.parent_item_group = %(parent_item_group)s"
            params["parent_item_group"] = self.parent_item_group

        query = f"""
            SELECT SUM(si_item.qty) AS qty
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
            INNER JOIN `tabItem` i ON si_item.item_code = i.name
            INNER JOIN `tabItem Group` ig ON i.item_group = ig.name
            INNER JOIN `tabCustomer Mapping` cm ON si.customer = cm.customer
            INNER JOIN `tabSales Rep Info` b ON cm.parent = b.name
            WHERE si.docstatus = 1
                AND si.is_return = 0
                AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND b.sales_rep = %(sales_rep)s
                {conditions}
        """

        qty = frappe.db.sql(query, params, as_dict=True)[0].qty or 0
        return qty

    def get_total_stores(self, sales_rep):
        stores = frappe.db.sql("""
            SELECT COUNT(DISTINCT cm.customer) AS store_count
            FROM `tabCustomer Mapping` cm
            INNER JOIN `tabSales Rep Info` b ON cm.parent = b.name
            WHERE b.sales_rep = %s
        """, (sales_rep,), as_dict=True)[0].store_count or 0

        return stores

    def get_columns(self):
        return [
            {"label": _("Sales Rep"), "fieldname": "sales_rep", "fieldtype": "Data", "width": 200},
            {"label": _("Total Units Billed"), "fieldname": "total_units", "fieldtype": "Float", "width": 150},
            {"label": _("Total Stores"), "fieldname": "total_stores", "fieldtype": "Int", "width": 120},
            {"label": _("Productivity (Units / Store)"), "fieldname": "productivity", "fieldtype": "Float", "width": 180},
        ]


def execute(filters=None):
    return SalesRepProductivityReport(filters).run()
