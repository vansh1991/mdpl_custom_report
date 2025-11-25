import frappe
from frappe import _, qb, scrub
from frappe.query_builder import Criterion, Tuple
from frappe.query_builder.functions import IfNull
from frappe.utils import getdate, nowdate, add_days
from frappe.utils.nestedset import get_descendants_of
from pypika.terms import LiteralValue
from pypika.functions import Count, Sum
from pypika import CustomFunction  # Added for DATEDIFF
from pypika import CustomFunction, Query, Table  # <- add Query and Table here
from pypika.functions import Max


from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
    get_dimension_with_children,
)

TREE_DOCTYPES = frozenset(
    [
        "Customer Group",
        "Territory",
        "Supplier Group",
        "Sales Partner",
        "Sales Person",
        "Cost Center",
    ]
)


class PartyLedgerSummaryReport:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.filters.from_date = getdate(self.filters.from_date or nowdate())
        self.filters.to_date = getdate(self.filters.to_date or nowdate())
        self.filters.apple_id = self.filters.get("apple_id", 0)
        self.ranges = [
            int(num.strip())
            for num in self.filters.get("avg_outstanding_ranges", "10").split(",")
            if num.strip().isdigit() and int(num.strip()) > 0
        ]
        self.ranges = sorted(self.ranges)
        if not self.ranges:
            frappe.throw(
                _(
                    "Average outstanding ranges must contain at least one valid positive integer"
                )
            )
        self.max_days = max(self.ranges) if self.ranges else 0

    def run(self, args):
        self.filters.party_type = args.get("party_type")
        self.validate_filters()
        self.get_party_details()
        self.get_last_invoice_date()
        if not self.parties:
            return [], []
        self.get_gl_entries()
        self.calculate_closing_balances()
        self.prepare_invoiced_amounts()
        self.get_return_invoices()
        self.get_party_adjustment_amounts()
        self.get_cheque_count()
        self.get_average_outstanding()
        self.party_naming_by = frappe.db.get_single_value(
            args.get("naming_by")[0], args.get("naming_by")[1]
        )
        columns = self.get_columns()
        data = self.get_data()
        return columns, data



    def calculate_closing_balances(self):
        invoice_dr_or_cr = (
            "debit" if self.filters.party_type == "Customer" else "credit"
        )
        reverse_dr_or_cr = (
            "credit" if self.filters.party_type == "Customer" else "debit"
        )
        self.closing_balances = frappe._dict()
        for gle in self.gl_entries:
            party = gle.party
            amount = gle.get(invoice_dr_or_cr, 0) - gle.get(reverse_dr_or_cr, 0)
            self.closing_balances[party] = self.closing_balances.get(party, 0) + amount

    def prepare_invoiced_amounts(self):
        self.min_date = (
            add_days(self.filters.to_date, -self.max_days)
            if self.max_days > 0
            else self.filters.to_date
        )
        self.invoiced_amounts = frappe._dict()
        for party in self.parties:
            self.invoiced_amounts[party] = {idx: 0.0 for idx in range(len(self.ranges))}
        invoice_dr_or_cr = (
            "debit" if self.filters.party_type == "Customer" else "credit"
        )
        voucher_types = (
            ["Sales Invoice", "Journal Entry"]
            if self.filters.party_type == "Customer"
            else ["Purchase Invoice", "Journal Entry"]
        )
        for gle in self.gl_entries:
            if gle.party not in self.parties or gle.posting_date < self.min_date:
                continue
            if (
                gle.get(invoice_dr_or_cr, 0) > 0
                and gle.is_opening == "No"
                and gle.voucher_type in voucher_types
            ):
                days_ago = (self.filters.to_date - gle.posting_date).days
                for idx, days_range in enumerate(self.ranges):
                    if days_ago <= days_range:
                        self.invoiced_amounts[gle.party][idx] += gle.get(
                            invoice_dr_or_cr, 0
                        )

    def get_average_outstanding(self):
        self.avg_outstanding = frappe._dict()
        for party in self.parties:
            closing_balance = self.closing_balances.get(party, 0)
            self.avg_outstanding[party] = frappe._dict()
            for idx, days_range in enumerate(self.ranges):
                invoiced_amount = self.invoiced_amounts.get(party, {}).get(idx, 0)
                avg_balance = max(closing_balance - invoiced_amount, 0)
                self.avg_outstanding[party][idx] = round(avg_balance, 2)

    def get_average_outstanding_for_customer(self, customer, days_range):
        closing_balance = self.closing_balances.get(customer, 0)
        idx = self.ranges.index(days_range) if days_range in self.ranges else -1
        invoiced_amount = (
            self.invoiced_amounts.get(customer, {}).get(idx, 0) if idx != -1 else 0
        )
        avg_balance = max(closing_balance - invoiced_amount, 0)
        return avg_balance

    def get_first_invoiced_for_customer(self, customer, days_range):
        idx = self.ranges.index(days_range) if days_range in self.ranges else -1
        return self.invoiced_amounts.get(customer, {}).get(idx, 0) if idx != -1 else 0

    def validate_filters(self):
        if not self.filters.get("company"):
            frappe.throw(_("{0} is mandatory").format(_("Company")))
        if self.filters.from_date > self.filters.to_date:
            frappe.throw(_("From Date must be before To Date"))
        self.update_hierarchical_filters()

    def update_hierarchical_filters(self):
        for doctype in TREE_DOCTYPES:
            key = scrub(doctype)
            if self.filters.get(key):
                self.filters[key] = get_children(doctype, self.filters[key])

    def get_party_details(self):
        self.parties = []
        self.party_details = frappe._dict()
        party_type = self.filters.party_type
        doctype = qb.DocType(party_type)
        conditions = self.get_party_conditions(doctype)
        query = (
            qb.from_(doctype)
            .select(
                doctype.name.as_("party"),
                f"{scrub(party_type)}_name",
                IfNull(doctype.apple_id, "").as_("apple_id"),
            )
            .where(Criterion.all(conditions))
        )
        from frappe.desk.reportview import build_match_conditions

        match_conditions = build_match_conditions(party_type)
        if match_conditions:
            query = query.where(LiteralValue(match_conditions))
        party_details = query.run(as_dict=True)
        for row in party_details:
            self.parties.append(row.party)
            self.party_details[row.party] = row

    def get_cheque_count(self):
        """Compute cheque counts, amounts, and last received cheque date for Customers."""
        if self.filters.party_type != "Customer":
            self.cheque_counts = frappe._dict()
            return

        pe = qb.DocType("Payment Entry")
        query = (
            qb.from_(pe)
            .select(
                pe.party,
                pe.workflow_state,
                Count("*").as_("count"),
                Sum(pe.paid_amount).as_("total_amount"),
                Max(pe.posting_date).as_("last_received_cheque_date"),
            )
            .where(
                (pe.party_type == "Customer")
                & (pe.party.isin(self.parties))
                & (pe.workflow_state.isin(["Cheque Received", "Cheque Deposited"]))
                & (pe.posting_date.between(self.filters.from_date, self.filters.to_date))
            )
            .groupby(pe.party, pe.workflow_state)
        )

        results = query.run(as_dict=True)

        # Initialize cheque_counts for all parties
        self.cheque_counts = frappe._dict({
            party: {
                "cheque_received_count": 0,
                "cheque_received_amount": 0.0,
                "cheque_deposited_count": 0,
                "cheque_deposited_amount": 0.0,
                "last_received_cheque_date": None,
            }
            for party in self.parties
        })

        for row in results:
            party_data = self.cheque_counts[row.party]
            if row.workflow_state == "Cheque Received":
                party_data["cheque_received_count"] = row["count"] or 0
                party_data["cheque_received_amount"] = row["total_amount"] or 0.0
                party_data["last_received_cheque_date"] = row["last_received_cheque_date"]
            elif row.workflow_state == "Cheque Deposited":
                party_data["cheque_deposited_count"] = row["count"] or 0
                party_data["cheque_deposited_amount"] = row["total_amount"] or 0.0

	
    def get_last_invoice_date(self):
        self.last_invoice_dates = frappe._dict()
        if not self.parties:
            return

        invoice_doctype = "Sales Invoice" if self.filters.party_type == "Customer" else "Purchase Invoice"
        invoices = frappe.get_all(
            invoice_doctype,
            filters={
                f"{scrub(self.filters.party_type)}": ["in", self.parties],
                "docstatus": 1,
            },
            fields=["name", "posting_date", scrub(self.filters.party_type)],
            order_by="posting_date desc",
        )

        for inv in invoices:
            party = inv[scrub(self.filters.party_type)]
            if party not in self.last_invoice_dates:
                self.last_invoice_dates[party] = inv["posting_date"]


    def get_party_conditions(self, doctype):
        conditions = []
        group_field = "customer_group" if self.filters.party_type == "Customer" else "supplier_group"
        if self.filters.party:
            conditions.append(doctype.name == self.filters.party)
        if self.filters.territory:
            conditions.append(doctype.territory.isin(self.filters.territory))
        if self.filters.get(group_field):
            conditions.append(doctype[group_field].isin(self.filters.get(group_field)))
        if self.filters.payment_terms_template:
            conditions.append(doctype.payment_terms == self.filters.payment_terms_template)
        if self.filters.sales_partner:
            conditions.append(doctype.default_sales_partner.isin(self.filters.sales_partner))
                  
        sales_person = self.filters.get("sales_person")

        if sales_person:
        # If it’s a list, pick the first one
            if isinstance(sales_person, list):
                sales_person = sales_person[0] if sales_person else None

            if sales_person:  # only if still valid
                customer_mapping = Table("tabCustomer Mapping")
                sales_rep_info = Table("tabSales Rep Info")

                customers_subquery = (
                    Query.from_(customer_mapping)
                    .join(sales_rep_info)
                    .on(customer_mapping.parent == sales_rep_info.name)
                    .select(customer_mapping.customer)
                    .where(sales_rep_info.name == sales_person)
                )
                conditions.append(doctype.name.isin(customers_subquery))
        if self.filters.party_type == "Customer":
            if self.filters.apple_id:  # Checked: Show customers with Apple ID
                conditions.append(IfNull(doctype.apple_id, "") != "")
            else:  # Unchecked: Show customers without Apple ID
                conditions.append(IfNull(doctype.apple_id, "") == "")
        return conditions


    def get_columns(self):
        columns = [
            {
                "label": _(self.filters.party_type),
                "fieldtype": "Link",
                "fieldname": "party",
                "options": self.filters.party_type,
                "width": 200,
            },
            {
                "label": _("Apple ID"),
                "fieldtype": "Check",
                "fieldname": "apple_id",
                "width": 100,
                "hidden": 1,
            },
        ]
        if self.party_naming_by == "Naming Series":
            columns.append(
                {
                    "label": _(self.filters.party_type + " Name"),
                    "fieldtype": "Data",
                    "fieldname": "party_name",
                    "width": 150,
                }
            )
        credit_or_debit_note = (
            "Credit Note" if self.filters.party_type == "Customer" else "Debit Note"
        )
        columns += [
            {
                "label": _("Opening Balance"),
                "fieldname": "opening_balance",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Invoiced Amount"),
                "fieldname": "invoiced_amount",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Paid Amount"),
                "fieldname": "paid_amount",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _(credit_or_debit_note),
                "fieldname": "return_amount",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
                "hidden": 1,
            },
        ]
        columns.append(
            {
                "label": _("Payment Due"),
                "fieldname": "payment_due",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
                "hidden": 1,
            }
        )
        if self.ranges:
            columns.append(
                {
                    "label": _("Due under {0} Days ").format(self.ranges[0]),
                    "fieldname": "first_invoiced_amount",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "width": 150,
                }
            )
        for idx, range_end in enumerate(self.ranges):
            range_start = 0 if idx == 0 else self.ranges[idx - 1]
            columns.append(
                {
                    "label": _("Overdue more than {1} Days").format(
                        range_start, range_end
                    ),
                    "fieldname": f"avg_outstanding_{idx + 1}",
                    "fieldtype": "Currency",
                    "options": "currency",
                    "width": 150,
                }
            )
        for account in self.party_adjustment_accounts:
            columns.append(
                {
                    "label": account,
                    "fieldname": "adj_" + scrub(account),
                    "fieldtype": "Currency",
                    "options": "currency",
                    "width": 120,
                    "is_adjustment": 1,
                    "hidden": 1,
                }
            )
        columns += [
            {
                "label": _("Closing Balance"),
                "fieldname": "closing_balance",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Currency"),
                "fieldname": "currency",
                "fieldtype": "Link",
                "options": "Currency",
                "width": 50,
                "hidden": 1,
            },
        ]
        if self.filters.party_type == "Customer":
            columns += [
                {
                    "label": _("Territory"),
                    "fieldname": "territory",
                    "fieldtype": "Link",
                    "options": "Territory",
                    "hidden": 1,
                },
                {
                    "label": _("Customer Group"),
                    "fieldname": "customer_group",
                    "fieldtype": "Link",
                    "options": "Customer Group",
                    "hidden": 1,
                },
                {
                    "label": _("Cheque Received Count"),
                    "fieldtype": "Int",
                    "fieldname": "cheque_received_count",
                    "width": 150,
                },
                {
                    "label": _("Cheque Received Amount"),
                    "fieldtype": "Currency",
                    "fieldname": "cheque_received_amount",
                    "width": 150,
                },
                {
                    "label": _("Cheque Deposited Count"),
                    "fieldtype": "Int",
                    "fieldname": "cheque_deposited_count",
                    "width": 150,
                },
                {
                    "label": _("Cheque Deposited Amount"),
                    "fieldtype": "Currency",
                    "fieldname": "cheque_deposited_amount",
                    "width": 150,
                },
				{
					"label": _("Last Received Cheque Date"),
					"fieldtype": "Date",
					"fieldname": "last_received_cheque_date",
					"width": 150,
				},
				{
					"label": _("Last Invoice Date"),
					"fieldtype": "Date",
					"fieldname": "last_invoice_date",
					"width": 150,
				},
            ]
        else:
            columns += [
                {
                    "label": _("Supplier Group"),
                    "fieldname": "supplier_group",
                    "fieldtype": "Link",
                    "options": "Supplier Group",
                    "hidden": 1,
                }
            ]
        return columns

    def get_data(self):
        company_currency = frappe.get_cached_value(
            "Company", self.filters.get("company"), "default_currency"
        )
        invoice_dr_or_cr = "debit" if self.filters.party_type == "Customer" else "credit"
        reverse_dr_or_cr = "credit" if self.filters.party_type == "Customer" else "debit"

        self.party_data = frappe._dict()

        for gle in self.gl_entries:
            party_details = self.party_details.get(gle.party, {})
            party_name = party_details.get(f"{scrub(self.filters.party_type)}_name", "")
            apple_id_status = 1 if party_details.get("apple_id") else 0

            # Prepare avg_outstanding flattened dict
            avg_outstanding_dict = {
                f"avg_outstanding_{idx + 1}": self.avg_outstanding.get(gle.party, {}).get(idx, 0)
                for idx in range(len(self.ranges))
            }

            # Initialize party data if not exists
            self.party_data.setdefault(
                gle.party,
                frappe._dict(
                    {
                        **party_details,
                        "party_name": party_name,
                        "opening_balance": 0.0,
                        "invoiced_amount": 0.0,
                        "paid_amount": 0.0,
                        "return_amount": 0.0,
                        "closing_balance": 0.0,
                        "currency": company_currency,
                        "payment_due": 0.0,
                        "apple_id": apple_id_status,
                        "first_invoiced_amount": self.get_first_invoiced_for_customer(
                            gle.party, self.ranges[0]
                        ) if self.ranges else 0.0,
                        **avg_outstanding_dict,  # Flatten here
                        "last_received_cheque_date": None,
                        "last_invoice_date": None,
                    }
                ),
            )

            party_row = self.party_data[gle.party]

            # Update balances
            amount = gle.get(invoice_dr_or_cr, 0) - gle.get(reverse_dr_or_cr, 0)
            party_row.closing_balance += amount
            if gle.posting_date < self.filters.from_date or gle.is_opening == "Yes":
                party_row.opening_balance += amount
            else:
                if amount > 0:
                    party_row.invoiced_amount += amount
                elif gle.voucher_no in self.return_invoices:
                    party_row.return_amount -= amount
                else:
                    party_row.paid_amount -= amount

        # Fill cheque and last invoice dates
        for party, row in self.party_data.items():
            cheque_data = self.cheque_counts.get(party, {})
            row.cheque_received_count = cheque_data.get("cheque_received_count", 0)
            row.cheque_received_amount = cheque_data.get("cheque_received_amount", 0.0)
            row.cheque_deposited_count = cheque_data.get("cheque_deposited_count", 0)
            row.cheque_deposited_amount = cheque_data.get("cheque_deposited_amount", 0.0)
            row.last_received_cheque_date = cheque_data.get("last_received_cheque_date")
            row.last_invoice_date = self.last_invoice_dates.get(party)

            # Apply party adjustments
            total_party_adjustment = sum(
                amount for amount in self.party_adjustment_details.get(party, {}).values()
            )
            row.paid_amount -= total_party_adjustment
            for account in self.party_adjustment_accounts:
                row["adj_" + scrub(account)] = self.party_adjustment_details.get(party, {}).get(account, 0)

        return list(self.party_data.values())



    def get_gl_entries(self):
        gle = qb.DocType("GL Entry")
        query = (
            qb.from_(gle)
            .select(
                gle.posting_date,
                gle.party,
                gle.voucher_type,
                gle.voucher_no,
                gle.debit,
                gle.credit,
                gle.is_opening,
            )
            .where(
                (gle.docstatus < 2)
                & (gle.is_cancelled == 0)
                & (gle.party_type == self.filters.party_type)
                & (IfNull(gle.party, "") != "")
                & (gle.posting_date <= self.filters.to_date)
                & (gle.party.isin(self.parties))
            )
        )
        query = self.prepare_conditions(query)
        self.gl_entries = query.run(as_dict=True)

    def prepare_conditions(self, query):
        gle = qb.DocType("GL Entry")
        if self.filters.company:
            query = query.where(gle.company == self.filters.company)
        if self.filters.finance_book:
            query = query.where(
                IfNull(gle.finance_book, "") == self.filters.finance_book
            )
        if self.filters.cost_center:
            query = query.where((gle.cost_center).isin(self.filters.cost_center))
        if self.filters.project:
            query = query.where((gle.project).isin(self.filters.project))
        accounting_dimensions = get_accounting_dimensions(as_list=False)
        if accounting_dimensions:
            for dimension in accounting_dimensions:
                if self.filters.get(dimension.fieldname):
                    if frappe.get_cached_value(
                        "DocType", dimension.document_type, "is_tree"
                    ):
                        self.filters[dimension.fieldname] = get_dimension_with_children(
                            dimension.document_type,
                            self.filters.get(dimension.fieldname),
                        )
                        query = query.where(
                            (gle[dimension.fieldname]).isin(
                                self.filters.get(dimension.fieldname)
                            )
                        )
                    else:
                        query = query.where(
                            (gle[dimension.fieldname]).isin(
                                self.filters.get(dimension.fieldname)
                            )
                        )
        return query

    def get_return_invoices(self):
        doctype = (
            "Sales Invoice"
            if self.filters.party_type == "Customer"
            else "Purchase Invoice"
        )
        filters = {
            "is_return": 1,
            "docstatus": 1,
            "posting_date": ["between", [self.filters.from_date, self.filters.to_date]],
            f"{scrub(self.filters.party_type)}": ["in", self.parties],
        }
        self.return_invoices = frappe.get_all(doctype, filters=filters, pluck="name")

    def get_party_adjustment_amounts(self):
        account_type = (
            "Expense Account"
            if self.filters.party_type == "Customer"
            else "Income Account"
        )
        invoice_dr_or_cr = (
            "debit" if self.filters.party_type == "Customer" else "credit"
        )
        reverse_dr_or_cr = (
            "credit" if self.filters.party_type == "Customer" else "debit"
        )
        round_off_account = frappe.get_cached_value(
            "Company", self.filters.company, "round_off_account"
        )
        current_period_vouchers = set()
        adjustment_voucher_entries = {}
        self.party_adjustment_details = {}
        self.party_adjustment_accounts = set()
        for gle in self.gl_entries:
            if (
                gle.is_opening != "Yes"
                and gle.posting_date >= self.filters.from_date
                and gle.posting_date <= self.filters.to_date
            ):
                current_period_vouchers.add((gle.voucher_type, gle.voucher_no))
                adjustment_voucher_entries.setdefault(
                    (gle.voucher_type, gle.voucher_no), []
                ).append(gle)
        if not current_period_vouchers:
            return
        gl = qb.DocType("GL Entry")
        query = (
            qb.from_(gl)
            .select(
                gl.posting_date,
                gl.account,
                gl.party,
                gl.voucher_type,
                gl.voucher_no,
                gl.debit,
                gl.credit,
            )
            .where(
                (gl.docstatus < 2)
                & (gl.is_cancelled == 0)
                & (gl.posting_date.gte(self.filters.from_date))
                & (gl.posting_date.lte(self.filters.to_date))
                & (
                    Tuple((gl.voucher_type, gl.voucher_no)).isin(
                        current_period_vouchers
                    )
                )
                & (IfNull(gl.party, "") == "")
            )
        )
        query = self.prepare_conditions(query)
        gl_entries = query.run(as_dict=True)
        for gle in gl_entries:
            adjustment_voucher_entries[(gle.voucher_type, gle.voucher_no)].append(gle)
        for voucher_gl_entries in adjustment_voucher_entries.values():
            parties = {}
            accounts = {}
            has_irrelevant_entry = False
            for gle in voucher_gl_entries:
                if gle.account == round_off_account:
                    continue
                elif gle.party:
                    parties.setdefault(gle.party, 0)
                    parties[gle.party] += gle.get(reverse_dr_or_cr) - gle.get(
                        invoice_dr_or_cr
                    )
                elif (
                    frappe.get_cached_value("Account", gle.account, "account_type")
                    == account_type
                ):
                    accounts.setdefault(gle.account, 0)
                    accounts[gle.account] += gle.get(invoice_dr_or_cr) - gle.get(
                        reverse_dr_or_cr
                    )
                else:
                    has_irrelevant_entry = True
            if parties and accounts:
                if len(parties) == 1:
                    party = next(iter(parties.keys()))
                    for account, amount in accounts.items():
                        self.party_adjustment_accounts.add(account)
                        self.party_adjustment_details.setdefault(party, {})
                        self.party_adjustment_details[party].setdefault(account, 0)
                        self.party_adjustment_details[party][account] += amount
                elif len(accounts) == 1 and not has_irrelevant_entry:
                    account = next(iter(accounts.keys()))
                    self.party_adjustment_accounts.add(account)
                    for party, amount in parties.items():
                        self.party_adjustment_details.setdefault(party, {})
                        self.party_adjustment_details[party].setdefault(account, 0)
                        self.party_adjustment_details[party][account] += amount


def get_children(doctype, value):
    if not isinstance(value, list):
        value = [d.strip() for d in value.strip().split(",") if d]
    all_children = []
    for d in value:
        all_children += get_descendants_of(doctype, d)
        all_children.append(d)
    return list(set(all_children))


def execute(filters=None):
    args = {
        "party_type": "Customer",
        "naming_by": ["Selling Settings", "cust_master_name"],
    }
    return PartyLedgerSummaryReport(filters).run(args)
