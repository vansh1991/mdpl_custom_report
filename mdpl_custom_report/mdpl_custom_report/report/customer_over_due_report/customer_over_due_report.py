import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days

class CustomerOverdueReport:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.from_date = getdate(self.filters.get("from_date") or nowdate())
        self.to_date = getdate(self.filters.get("to_date") or nowdate())
        
        # Generate dynamic daily date ranges between from_date and to_date
        total_days = (self.to_date - self.from_date).days + 1  # inclusive
        self.daily_dates = [add_days(self.from_date, i) for i in range(total_days)]

        # Set overdue days from filter
        overdue_input = self.filters.get("overdue_days") or "0"
        try:
            overdue_list = [int(x.strip()) for x in str(overdue_input).split(",")]
            self.overdue_days = max(overdue_list)  # take max for threshold
        except Exception:
            self.overdue_days = 0  # default

    def run(self):
        self.get_customers()
        self.get_gl_entries()
        self.calculate_dues_and_buckets()
        columns = self.get_columns()
        data = self.get_data()
        return columns, data

    def get_customers(self):
        conditions = []
        values = []

        # Apple ID filter logic
        apple_id_checked = self.filters.get("apple_id")  # True if checked, else None or False
        if apple_id_checked:
            conditions.append("apple_id IS NOT NULL AND apple_id != ''")
        else:
            conditions.append("apple_id IS NULL OR apple_id = ''")

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
        values = [self.to_date]

        if self.filters.get("company"):
            conditions.append("company=%s")
            values.append(self.filters.company)

        if self.filters.get("cost_center"):
            conditions.append("cost_center IN ({})".format(",".join(["%s"]*len(self.filters.cost_center))))
            values.extend(self.filters.cost_center)

        condition_sql = " AND ".join(conditions)

        query = f"""
            SELECT posting_date, party, debit, credit, voucher_type, voucher_no
            FROM `tabGL Entry`
            WHERE {condition_sql}
        """
        self.gl_entries = frappe.db.sql(query, values=values, as_dict=True)

    def calculate_dues_and_buckets(self):
        self.customer_data = {}
        for cust in self.customers:
            self.customer_data[cust] = {
                "customer_name": self.customers[cust].get("customer_name"),
                "total_due": 0.0,
                "total_payment": 0.0,
                "net_outstanding": 0.0,
                "daily": [0.0 for _ in self.daily_dates]
            }

        for gle in self.gl_entries:
            party = gle.party
            if party not in self.customers:
                continue

            debit = gle.debit or 0
            credit = gle.credit or 0
            net_amount = debit - credit

            # Calculate overdue days from posting_date to today
            days_overdue = (getdate(nowdate()) - getdate(gle.posting_date)).days

            # Only consider if overdue more than threshold
            if days_overdue < self.overdue_days:
                continue

            self.customer_data[party]["total_due"] += debit
            self.customer_data[party]["total_payment"] += credit
            self.customer_data[party]["net_outstanding"] += net_amount

            # Fill daily buckets if within from_date and to_date
            days_index = (getdate(gle.posting_date) - self.from_date).days
            if 0 <= days_index < len(self.daily_dates):
                self.customer_data[party]["daily"][days_index] += net_amount

    def get_columns(self):
        columns = [
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
            {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
            {"label": _("Total Due"), "fieldname": "total_due", "fieldtype": "Currency", "width": 120},
            {"label": _("Total Payment"), "fieldname": "total_payment", "fieldtype": "Currency", "width": 120},
            {"label": _("Net Outstanding"), "fieldname": "net_outstanding", "fieldtype": "Currency", "width": 120},
        ]

        # Daily buckets as columns
        for idx, date in enumerate(self.daily_dates):
            columns.append({
                "label": _(date.strftime("%Y-%m-%d")),
                "fieldname": f"daily_{idx+1}",
                "fieldtype": "Currency",
                "width": 120
            })

        return columns

    def get_data(self):
        data = []
        for cust, row in self.customer_data.items():
            doc = {
                "customer": cust,
                "customer_name": row.get("customer_name"),
                "total_due": row.get("total_due"),
                "total_payment": row.get("total_payment"),
                "net_outstanding": row.get("net_outstanding")
            }

            # Fill daily values
            for idx, val in enumerate(row.get("daily", [])):
                doc[f"daily_{idx+1}"] = val

            data.append(doc)
        return data

def execute(filters=None):
    return CustomerOverdueReport(filters).run()
