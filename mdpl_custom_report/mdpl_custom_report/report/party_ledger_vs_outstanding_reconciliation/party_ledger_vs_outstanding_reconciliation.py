import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 100},
        {"label": _("Party"), "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 150},
        {"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
        {"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 160},
        {"label": _("Outstanding (Invoices)"), "fieldname": "invoice_outstanding", "fieldtype": "Currency", "width": 170},
        {"label": _("GL Balance"), "fieldname": "gl_balance", "fieldtype": "Currency", "width": 130},
        {"label": _("Unallocated Payments"), "fieldname": "unallocated_payments", "fieldtype": "Currency", "width": 170},
        {"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "width": 130},
    ]


def get_data(filters):
    result = []

    if filters.get("party_type"):
        party_types = [filters.get("party_type")]
    else:
        party_types = ["Customer", "Supplier"]

    for party_type in party_types:
        invoice_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
        invoice_data = get_invoice_outstanding(invoice_doctype, party_type, filters)
        gl_data = get_gl_balance(party_type, filters)
        unalloc_data = get_unallocated_payments(party_type, filters)

        keys = set(invoice_data.keys()) | set(gl_data.keys()) | set(unalloc_data.keys())

        for key in keys:
            party, company, account = key
            inv_row = invoice_data.get(key, {})
            gl_row = gl_data.get(key, {})
            unalloc_row = unalloc_data.get(key, {})

            invoice_outstanding = flt(inv_row.get("outstanding"))
            gl_balance = flt(gl_row.get("balance"))
            unallocated_payments = flt(unalloc_row.get("unallocated"))

            # Recalculated difference: nets out payments received/paid but not yet
            # allocated against a specific invoice. If this is ~0, the gap between
            # Outstanding and GL Balance is fully explained by pending allocation
            # (run Payment Reconciliation). If not, it needs manual investigation.
            difference = flt(invoice_outstanding - gl_balance - unallocated_payments, 2)

            if filters.get("show_difference_only") and abs(difference) < 0.01:
                continue

            result.append({
                "party_type": party_type,
                "party": party,
                "party_name": inv_row.get("party_name") or gl_row.get("party_name") or unalloc_row.get("party_name"),
                "company": company,
                "account": account,
                "invoice_outstanding": invoice_outstanding,
                "gl_balance": gl_balance,
                "unallocated_payments": unallocated_payments,
                "difference": difference,
            })

    result.sort(key=lambda r: abs(r["difference"]), reverse=True)
    return result


def get_invoice_outstanding(doctype, party_type, filters):
    party_field = "customer" if party_type == "Customer" else "supplier"
    party_name_field = "customer_name" if party_type == "Customer" else "supplier_name"
    account_field = "debit_to" if party_type == "Customer" else "credit_to"

    conditions = ["docstatus = 1"]
    values = {}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]
    if filters.get("party"):
        conditions.append(f"{party_field} = %(party)s")
        values["party"] = filters["party"]
    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    condition_str = " and ".join(conditions)

    rows = frappe.db.sql(f"""
        select
            {party_field} as party,
            {party_name_field} as party_name,
            company,
            {account_field} as account,
            sum(outstanding_amount) as outstanding
        from `tab{doctype}`
        where {condition_str}
        group by {party_field}, company, account
    """, values, as_dict=True)

    data = {}
    for row in rows:
        key = (row.party, row.company, row.account)
        data[key] = row
    return data


def get_gl_balance(party_type, filters):
    conditions = ["is_cancelled = 0", "party_type = %(party_type)s", "party is not null", "party != ''"]
    values = {"party_type": party_type}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]
    if filters.get("party"):
        conditions.append("party = %(party)s")
        values["party"] = filters["party"]
    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    condition_str = " and ".join(conditions)

    balance_expr = "sum(debit) - sum(credit)" if party_type == "Customer" else "sum(credit) - sum(debit)"

    rows = frappe.db.sql(f"""
        select
            party,
            company,
            account,
            {balance_expr} as balance
        from `tabGL Entry`
        where {condition_str}
        group by party, company, account
    """, values, as_dict=True)

    data = {}
    for row in rows:
        key = (row.party, row.company, row.account)
        data[key] = row
    return data


def get_unallocated_payments(party_type, filters):
    # Receive: party's receivable account is paid_from. Pay: party's payable account is paid_to.
    payment_type = "Receive" if party_type == "Customer" else "Pay"
    account_field = "paid_from" if party_type == "Customer" else "paid_to"
    party_name_field = "party_name"

    conditions = [
        "docstatus = 1",
        "party_type = %(party_type)s",
        "payment_type = %(payment_type)s",
        "unallocated_amount > 0",
    ]
    values = {"party_type": party_type, "payment_type": payment_type}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]
    if filters.get("party"):
        conditions.append("party = %(party)s")
        values["party"] = filters["party"]
    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    condition_str = " and ".join(conditions)

    rows = frappe.db.sql(f"""
        select
            party,
            {party_name_field} as party_name,
            company,
            {account_field} as account,
            sum(unallocated_amount) as unallocated
        from `tabPayment Entry`
        where {condition_str}
        group by party, company, account
    """, values, as_dict=True)

    data = {}
    for row in rows:
        key = (row.party, row.company, row.account)
        data[key] = row
    return data