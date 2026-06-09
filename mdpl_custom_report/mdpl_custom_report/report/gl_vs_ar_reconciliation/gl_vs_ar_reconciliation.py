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
        {"label": _("Customer"),           "fieldname": "party",          "fieldtype": "Link",     "options": "Customer", "width": 220},
        {"label": _("AR Outstanding"),     "fieldname": "ar_outstanding", "fieldtype": "Currency", "width": 140},
        {"label": _("JV Debit (Bounces)"), "fieldname": "jv_debit",       "fieldtype": "Currency", "width": 140},
        {"label": _("JV Recovered"),       "fieldname": "jv_recovered",   "fieldtype": "Currency", "width": 140},
        {"label": _("JV Unrecovered"),     "fieldname": "jv_unrecovered", "fieldtype": "Currency", "width": 140},
        {"label": _("Adjusted AR"),        "fieldname": "adjusted_ar",    "fieldtype": "Currency", "width": 140},
        {"label": _("GL Balance"),         "fieldname": "gl_balance",     "fieldtype": "Currency", "width": 140},
        {"label": _("GL Adjusted"),        "fieldname": "gl_adjusted",    "fieldtype": "Currency", "width": 140},
        {"label": _("Difference"),         "fieldname": "difference",     "fieldtype": "Currency", "width": 120},
        {"label": _("Status"),             "fieldname": "status",         "fieldtype": "Data",     "width": 280},
    ]


def get_data(filters):
    company     = filters.get("company")
    report_date = filters.get("report_date") or frappe.utils.today()
    customer    = filters.get("customer")

    customer_filter    = "AND gle.party = %(customer)s" if customer else ""
    customer_filter_si = "AND customer = %(customer)s"  if customer else ""

    # Get Receivable accounts for this company
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

    # ── STEP 1: True GL Balance per customer (Debtors account only) ──────────
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

    # ── STEP 2: JV Debit per customer per JV voucher ─────────────────────────
    jv_rows = frappe.db.sql("""
        SELECT
            gle.party,
            gle.voucher_no,
            SUM(gle.debit)  AS jv_debit,
            SUM(gle.credit) AS jv_credit
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE
            gle.company          = %(company)s
            AND gle.posting_date <= %(report_date)s
            AND gle.is_cancelled  = 0
            AND gle.party_type    = 'Customer'
            AND gle.party IS NOT NULL
            AND gle.voucher_type  = 'Journal Entry'
            AND acc.account_type  = 'Receivable'
            {customer_filter}
        GROUP BY gle.party, gle.voucher_no
    """.format(customer_filter=customer_filter), params, as_dict=1)

    # ── STEP 3: Payments linked to each JV via against_voucher ───────────────
    jv_payment_rows = frappe.db.sql("""
        SELECT
            gle.party,
            gle.against_voucher  AS jv_voucher,
            SUM(gle.credit)      AS paid_against_jv
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE
            gle.company                  = %(company)s
            AND gle.posting_date        <= %(report_date)s
            AND gle.is_cancelled         = 0
            AND gle.party_type           = 'Customer'
            AND gle.voucher_type         = 'Payment Entry'
            AND gle.against_voucher_type = 'Journal Entry'
            AND gle.credit               > 0
            AND acc.account_type         = 'Receivable'
            {customer_filter}
        GROUP BY gle.party, gle.against_voucher
    """.format(customer_filter=customer_filter), params, as_dict=1)

    # Build map: {party: {jv_voucher: paid_amount}}
    jv_payment_map = {}
    for r in jv_payment_rows:
        jv_payment_map.setdefault(r.party, {})
        jv_payment_map[r.party][r.jv_voucher] = flt(r.paid_against_jv)

    # Per customer: JV debit, recovered (capped at JV debit), unrecovered
    jv_summary = {}
    for r in jv_rows:
        party  = r.party
        jv_no  = r.voucher_no
        jv_net = flt(r.jv_debit) - flt(r.jv_credit)

        if jv_net <= 0:
            continue  # net credit JV — skip

        paid_for_jv = flt(jv_payment_map.get(party, {}).get(jv_no, 0))

        # Cap recovery at actual JV net debit (LEAST logic)
        recovered   = min(paid_for_jv, jv_net)
        unrecovered = jv_net - recovered

        jv_summary.setdefault(party, {"jv_debit": 0, "jv_recovered": 0, "jv_unrecovered": 0})
        jv_summary[party]["jv_debit"]       += jv_net
        jv_summary[party]["jv_recovered"]   += recovered
        jv_summary[party]["jv_unrecovered"] += unrecovered

    # ── STEP 4: AR Outstanding from Sales Invoice table ──────────────────────
    ar_rows = frappe.db.sql("""
        SELECT
            customer AS party,
            SUM(outstanding_amount) AS ar_outstanding
        FROM `tabSales Invoice`
        WHERE
            docstatus        = 1
            AND company      = %(company)s
            AND posting_date <= %(report_date)s
            {customer_filter_si}
        GROUP BY customer
    """.format(customer_filter_si=customer_filter_si), params, as_dict=1)

    ar_map = {r.party: flt(r.ar_outstanding) for r in ar_rows}

    # ── STEP 5: Merge and compute ─────────────────────────────────────────────
    data = []
    for party in set(gl_balance_map.keys()):
        gl_balance     = gl_balance_map.get(party, 0)
        ar_outstanding = ar_map.get(party, 0)

        jv             = jv_summary.get(party, {})
        jv_debit       = flt(jv.get("jv_debit",       0))
        jv_recovered   = flt(jv.get("jv_recovered",   0))
        jv_unrecovered = flt(jv.get("jv_unrecovered", 0))

        # Adjusted AR  = AR outstanding + unrecovered JV debits
        adjusted_ar = ar_outstanding + jv_unrecovered

        # GL Adjusted  = GL balance + recovered JV amounts
        gl_adjusted = gl_balance + jv_recovered

        # Final difference — should be 0 after adjustment
        difference = flt(adjusted_ar) - flt(gl_adjusted)

        # Skip zero balance customers
        if abs(gl_balance) < 0.5 and abs(ar_outstanding) < 0.5:
            continue

        # Status
        if abs(difference) < 1:
            status = "✅ Match"
        elif jv_unrecovered > 0:
            status = "⚠️ Bounce ₹{:,.0f} not yet collected".format(jv_unrecovered)
        elif gl_balance < 0 and abs(ar_outstanding) < 1:
            status = "⚠️ GL Credit — excess payment unallocated"
        elif gl_balance < 0:
            status = "⚠️ GL Credit — customer overpaid"
        elif difference > 0:
            status = "⚠️ AR > GL — check payment GL linking"
        else:
            status = "⚠️ GL > AR — unmatched GL entries"

        data.append({
            "party":          party,
            "ar_outstanding": ar_outstanding,
            "jv_debit":       jv_debit,
            "jv_recovered":   jv_recovered,
            "jv_unrecovered": jv_unrecovered,
            "adjusted_ar":    adjusted_ar,
            "gl_balance":     gl_balance,
            "gl_adjusted":    gl_adjusted,
            "difference":     difference,
            "status":         status,
        })

    # Sort: unmatched first, then by absolute difference descending
    data.sort(key=lambda x: (0 if "✅" in x["status"] else 1, -abs(x["difference"])))
    return data
