# Copyright (c) 2024, Mahesh Distributor Pvt Ltd
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Customer"),           "fieldname": "party",            "fieldtype": "Link",     "options": "Customer", "width": 220},
        {"label": _("AR Outstanding"),     "fieldname": "ar_outstanding",   "fieldtype": "Currency", "width": 140},
        {"label": _("GL Balance"),         "fieldname": "gl_balance",       "fieldtype": "Currency", "width": 140},
        {"label": _("GL (Open Invoices)"), "fieldname": "gl_open_invoices", "fieldtype": "Currency", "width": 160},
        {"label": _("Difference"),         "fieldname": "difference",       "fieldtype": "Currency", "width": 120},
        {"label": _("Status"),             "fieldname": "status",           "fieldtype": "Data",     "width": 320},
    ]


def get_data(filters):
    company     = filters.get("company")
    report_date = filters.get("report_date") or frappe.utils.today()
    customer    = filters.get("customer")

    customer_filter    = "AND gle.party = %(customer)s" if customer else ""
    customer_filter_si = "AND si.customer = %(customer)s" if customer else ""
    customer_filter_si2 = "AND customer = %(customer)s" if customer else ""

    accounts = frappe.db.get_all(
        "Account",
        filters={"account_type": "Receivable", "company": company, "is_group": 0},
        pluck="name",
    )
    if not accounts:
        return []

    params = {
        "company":     company,
        "report_date": report_date,
        "customer":    customer,
        "accounts":    tuple(accounts),
    }

    # STEP 1: True GL Balance (whole ledger, for reference)
    gl_balance_rows = frappe.db.sql("""
        SELECT
            gle.party,
            SUM(gle.debit) - SUM(gle.credit) AS gl_balance
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE
            gle.company          = %(company)s
            AND gle.posting_date <= %(report_date)s
            AND gle.is_cancelled  = 0
            AND gle.party_type    = 'Customer'
            AND gle.party IS NOT NULL
            AND gle.party        != ''
            AND acc.account_type  = 'Receivable'
            {customer_filter}
        GROUP BY gle.party
    """.format(customer_filter=customer_filter), params, as_dict=1)

    gl_balance_map = {r.party: flt(r.gl_balance) for r in gl_balance_rows}

    # STEP 2: AR Outstanding from Sales Invoice table
    ar_rows = frappe.db.sql("""
        SELECT
            customer AS party,
            SUM(outstanding_amount) AS ar_outstanding
        FROM `tabSales Invoice`
        WHERE
            docstatus        = 1
            AND company      = %(company)s
            AND posting_date <= %(report_date)s
            {customer_filter_si2}
        GROUP BY customer
    """.format(customer_filter_si2=customer_filter_si2), params, as_dict=1)

    ar_map = {r.party: flt(r.ar_outstanding) for r in ar_rows}

    # STEP 3: GL balance restricted to OPEN invoices only
    gl_open_rows = frappe.db.sql("""
        SELECT
            si.customer AS party,
            SUM(
                COALESCE(gle.debit, 0) - COALESCE(gle.credit, 0)
            ) AS gl_open_invoices
        FROM `tabSales Invoice` si
        LEFT JOIN `tabGL Entry` gle
            ON (
                (gle.voucher_type = 'Sales Invoice' AND gle.voucher_no = si.name)
                OR
                (gle.against_voucher_type = 'Sales Invoice' AND gle.against_voucher = si.name)
            )
            AND gle.is_cancelled = 0
            AND gle.party_type = 'Customer'
            AND gle.account IN %(accounts)s
            AND gle.posting_date <= %(report_date)s
        WHERE
            si.docstatus     = 1
            AND si.company   = %(company)s
            AND si.posting_date <= %(report_date)s
            AND si.outstanding_amount != 0
            {customer_filter_si}
        GROUP BY si.customer
    """.format(customer_filter_si=customer_filter_si), params, as_dict=1)

    gl_open_map = {r.party: flt(r.gl_open_invoices) for r in gl_open_rows}

    # STEP 4: Merge and compute
    all_parties = set(gl_balance_map.keys()) | set(ar_map.keys())

    data = []
    for party in all_parties:
        gl_balance       = gl_balance_map.get(party, 0)
        ar_outstanding   = ar_map.get(party, 0)
        gl_open_invoices = gl_open_map.get(party, 0)

        difference = flt(ar_outstanding) - flt(gl_open_invoices)

        if abs(gl_balance) < 0.5 and abs(ar_outstanding) < 0.5:
            continue

        if abs(difference) < 1:
            status = "OK - AR matches GL (Open Invoices)"
        elif difference > 0:
            status = "WARNING - AR > GL - payment linked to wrong invoice in GL"
        else:
            status = "WARNING - GL > AR - extra GL credit on open invoice"

        full_gl_diff = flt(ar_outstanding) - flt(gl_balance)
        if abs(full_gl_diff) > 1 and abs(difference) < 1:
            status += " | Note: Full GL Balance differs by Rs {:,.0f} (historical JV/adjustment entries, not affecting open invoices)".format(full_gl_diff)

        data.append({
            "party":            party,
            "ar_outstanding":   ar_outstanding,
            "gl_balance":       gl_balance,
            "gl_open_invoices": gl_open_invoices,
            "difference":       difference,
            "status":           status,
        })

    data.sort(key=lambda x: (0 if x["status"].startswith("OK") else 1, -abs(x["difference"])))
    return data
