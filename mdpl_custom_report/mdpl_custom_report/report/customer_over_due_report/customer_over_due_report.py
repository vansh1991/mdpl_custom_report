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

        # FIX: overdue_days is a plain Int filter - no need to split on commas.
        # Previously the code did max() on a comma-split of an Int field, which
        # was dead code and would silently fall back to 0 for any normal input.
        try:
            self.overdue_days = int(self.filters.get("overdue_days") or 0)
        except (ValueError, TypeError):
            self.overdue_days = 0

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
        apple_id_checked = self.filters.get("apple_id")
        if apple_id_checked:
            conditions.append("apple_id IS NOT NULL AND apple_id != ''")
        else:
            conditions.append("(apple_id IS NULL OR apple_id = '')")

        if self.filters.get("customer"):
            conditions.append("name = %s")
            values.append(self.filters.customer)

        condition_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT name AS customer,
                   IFNULL(customer_name, '') AS customer_name
            FROM `tabCustomer`
            {condition_sql}
        """
        self.customers = {
            row.customer: row
            for row in frappe.db.sql(query, values=values, as_dict=True)
        }

    def get_gl_entries(self):
        # FIX: Removed `is_cancelled = 0` - this column does not exist on
        # tabGL Entry in standard Frappe/ERPNext.  Cancelled entries already
        # have docstatus = 2, so `docstatus < 2` is the correct guard.
        conditions = [
            "docstatus < 2",
            "party_type = 'Customer'",
            "party IS NOT NULL",
            "posting_date <= %s",
        ]
        values = [self.to_date]

        if self.filters.get("company"):
            conditions.append("company = %s")
            values.append(self.filters.company)

        # FIX: cost_center filter is a single Link field in the JS definition.
        # Accept both a scalar string and a list so the report works regardless
        # of how the front-end passes the value.
        cost_center = self.filters.get("cost_center")
        if cost_center:
            if isinstance(cost_center, (list, tuple)):
                placeholders = ", ".join(["%s"] * len(cost_center))
                conditions.append(f"cost_center IN ({placeholders})")
                values.extend(cost_center)
            else:
                conditions.append("cost_center = %s")
                values.append(cost_center)

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
                "daily": [0.0 for _ in self.daily_dates],
                "_daily_net": [0.0 for _ in self.daily_dates],
            }

        today = getdate(nowdate())

        for gle in self.gl_entries:
            party = gle.party
            if party not in self.customers:
                continue

            debit = gle.debit or 0
            credit = gle.credit or 0
            net_amount = debit - credit
            posting_date = getdate(gle.posting_date)

            # Overdue threshold gates the summary totals only.
            days_overdue = (today - posting_date).days
            if days_overdue >= self.overdue_days:
                self.customer_data[party]["total_due"] += debit
                self.customer_data[party]["total_payment"] += credit
                self.customer_data[party]["net_outstanding"] += net_amount

            # For the daily closing balance we need ALL GL entries up to
            # to_date, not just those within from_date..to_date.
            # Entries posted before from_date contribute to the opening
            # balance carried into every day (clamped to bucket 0).
            # Entries posted on a date within the range go to their exact bucket.
            clamped_index = max(0, (posting_date - self.from_date).days)
            if clamped_index < len(self.daily_dates):
                self.customer_data[party]["_daily_net"][clamped_index] += net_amount

        # Convert per-day net movements into cumulative closing balances
        # using a prefix-sum across the buckets.
        for cust, row in self.customer_data.items():
            running = 0.0
            for i, net in enumerate(row["_daily_net"]):
                running += net
                row["daily"][i] = running

    def get_columns(self):
        columns = [
            {
                "label": _("Customer"),
                "fieldname": "customer",
                "fieldtype": "Link",
                "options": "Customer",
                "width": 200,
            },
            {
                "label": _("Customer Name"),
                "fieldname": "customer_name",
                "fieldtype": "Data",
                "width": 200,
            },
            {
                "label": _("Total Due"),
                "fieldname": "total_due",
                "fieldtype": "Currency",
                "width": 120,
            },
            {
                "label": _("Total Payment"),
                "fieldname": "total_payment",
                "fieldtype": "Currency",
                "width": 120,
            },
            {
                "label": _("Net Outstanding"),
                "fieldname": "net_outstanding",
                "fieldtype": "Currency",
                "width": 120,
            },
        ]

        # Daily buckets as columns
        for idx, date in enumerate(self.daily_dates):
            columns.append(
                {
                    "label": _(date.strftime("%Y-%m-%d")),
                    "fieldname": f"daily_{idx + 1}",
                    "fieldtype": "Currency",
                    "width": 120,
                }
            )

        return columns

    def get_data(self):
        data = []
        for cust, row in self.customer_data.items():
            # Skip rows with no outstanding and no daily balance at all.
            if row.get("net_outstanding") == 0 and not any(row.get("daily", [])):
                continue

            doc = {
                "customer": cust,
                "customer_name": row.get("customer_name"),
                "total_due": row.get("total_due"),
                "total_payment": row.get("total_payment"),
                "net_outstanding": row.get("net_outstanding"),
            }

            for idx, val in enumerate(row.get("daily", [])):
                doc[f"daily_{idx + 1}"] = val

            data.append(doc)
        return data


def execute(filters=None):
    return CustomerOverdueReport(filters).run()