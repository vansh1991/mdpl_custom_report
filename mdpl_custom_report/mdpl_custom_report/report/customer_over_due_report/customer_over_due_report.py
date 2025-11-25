import frappe
from frappe import _
from frappe.utils import getdate, nowdate

class CustomerOverdueReport:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.filters.from_date = getdate(self.filters.get("from_date") or nowdate())
        self.filters.to_date = getdate(self.filters.get("to_date") or nowdate())

        self.daily_ranges = sorted([int(d) for d in self.filters.get("daily_ranges", "").split(",") if d.isdigit()])
        self.weekly_ranges = sorted([int(w) for w in self.filters.get("weekly_ranges", "").split(",") if w.isdigit()])
        self.overdue_type = self.filters.get("overdue_type", "Daily")  # Daily or Weekly

    def run(self):
        self.get_customers()
        self.get_gl_entries()
        self.calculate_overdue()
        columns = self.get_columns()
        data = self.get_data()
        return columns, data

    def get_customers(self):
        conditions = []
        values = []

        if self.filters.get("customer"):
            conditions.append("name=%s")
            values.append(self.filters.customer)

        condition_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT name as customer,
                   IFNULL(customer_name, '') as customer_name
            FROM `tabCustomer`
            {condition_sql}
        """
        self.customers = {row.customer: row for row in frappe.db.sql(query, values=values, as_dict=True)}

    def get_gl_entries(self):
        conditions = [
            "docstatus < 2",
            "is_cancelled = 0",
            "party_type = 'Customer'",
            "party IS NOT NULL",
            "posting_date <= %s"
        ]
        values = [self.filters.to_date]

        if self.filters.get("company"):
            conditions.append("company=%s")
            values.append(self.filters.company)
        if self.filters.get("cost_center"):
            conditions.append("cost_center IN ({})".format(",".join(["%s"]*len(self.filters.cost_center))))
            values.extend(self.filters.cost_center)

        condition_sql = " AND ".join(conditions)

        query = f"""
            SELECT posting_date, party, debit, credit, voucher_type, voucher_no, is_opening
            FROM `tabGL Entry`
            WHERE {condition_sql}
        """
        self.gl_entries = frappe.db.sql(query, values=values, as_dict=True)

    def calculate_overdue(self):
        self.customer_data = {}
        for cust in self.customers:
            self.customer_data[cust] = {
                "customer_name": self.customers[cust].get("customer_name"),
                "total_outstanding": 0.0,
                "daily": [0.0 for _ in self.daily_ranges],
                "weekly": [0.0 for _ in self.weekly_ranges]
            }

        for gle in self.gl_entries:
            party = gle.party
            if party not in self.customers:
                continue

            amount = (gle.debit or 0) - (gle.credit or 0)
            if amount <= 0:
                continue

            days_overdue = (self.filters.to_date - getdate(gle.posting_date)).days
            self.customer_data[party]["total_outstanding"] += amount

            if self.overdue_type.lower() == "daily":
                for idx, day_limit in enumerate(self.daily_ranges):
                    if days_overdue <= day_limit:
                        self.customer_data[party]["daily"][idx] += amount
            elif self.overdue_type.lower() == "weekly":
                weeks_overdue = days_overdue // 7
                for idx, week_limit in enumerate(self.weekly_ranges):
                    if weeks_overdue <= week_limit:
                        self.customer_data[party]["weekly"][idx] += amount

    def get_columns(self):
        columns = [
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
            {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
            {"label": _("Total Outstanding"), "fieldname": "total_outstanding", "fieldtype": "Currency", "options": "currency", "width": 120},
        ]

        if self.overdue_type.lower() == "daily":
            for idx, day_limit in enumerate(self.daily_ranges):
                columns.append({
                    "label": _("Overdue <= {0} Days").format(day_limit),
                    "fieldname": f"daily_{idx+1}",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "width": 120,
                })

        if self.overdue_type.lower() == "weekly":
            for idx, week_limit in enumerate(self.weekly_ranges):
                columns.append({
                    "label": _("Overdue <= {0} Weeks").format(week_limit),
                    "fieldname": f"weekly_{idx+1}",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "width": 120,
                })

        return columns

    def get_data(self):
        data = []
        for cust, row in self.customer_data.items():
            doc = {
                "customer": cust,
                "customer_name": row.get("customer_name"),
                "total_outstanding": row.get("total_outstanding"),
            }

            if self.overdue_type.lower() == "daily":
                for idx, val in enumerate(row.get("daily", [])):
                    doc[f"daily_{idx+1}"] = val

            if self.overdue_type.lower() == "weekly":
                for idx, val in enumerate(row.get("weekly", [])):
                    doc[f"weekly_{idx+1}"] = val

            data.append(doc)

        return data


def execute(filters=None):
    return CustomerOverdueReport(filters).run()
