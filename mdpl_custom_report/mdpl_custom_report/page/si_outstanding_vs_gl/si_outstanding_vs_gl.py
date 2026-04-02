# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt
import json


@frappe.whitelist()
def get_si_outstanding_vs_gl(filters=None):
    if not frappe.has_permission("Sales Invoice", "report"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    # 1. Fetch submitted Sales Invoices
    si_conditions = ["si.docstatus = 1"]
    si_params = {}

    if filters.get("customer"):
        si_conditions.append("si.customer = %(customer)s")
        si_params["customer"] = filters["customer"]

    if filters.get("company"):
        si_conditions.append("si.company = %(company)s")
        si_params["company"] = filters["company"]

    if filters.get("from_date"):
        si_conditions.append("si.posting_date >= %(from_date)s")
        si_params["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        si_conditions.append("si.posting_date <= %(to_date)s")
        si_params["to_date"] = filters["to_date"]

    invoices = frappe.db.sql("""
        SELECT
            si.name,
            si.customer,
            si.posting_date,
            si.grand_total,
            si.outstanding_amount,
            si.debit_to,
            si.company,
            si.status
        FROM `tabSales Invoice` si
        WHERE {conditions}
        ORDER BY si.posting_date DESC
    """.format(conditions=" AND ".join(si_conditions)),
        si_params, as_dict=True
    )

    if not invoices:
        return {"results": [], "summary": {"total": 0, "negative": 0, "mismatch": 0, "both": 0, "ok": 0}}

    si_names = [d.name for d in invoices]

    # 2. Fetch GL balances per invoice (no date filter - full lifetime balance)
    gl_data = frappe.db.sql("""
        SELECT
            voucher_no,
            SUM(debit) - SUM(credit) AS gl_balance
        FROM `tabGL Entry`
        WHERE
            voucher_type = 'Sales Invoice'
            AND voucher_no IN %(si_names)s
            AND account IN (
                SELECT name FROM `tabAccount`
                WHERE account_type IN ('Receivable', 'Bank', 'Cash')
            )
            AND is_cancelled = 0
        GROUP BY voucher_no
    """, {"si_names": si_names}, as_dict=True)

    gl_map = {d.voucher_no: flt(d.gl_balance) for d in gl_data}

    # 3. Fetch linked payment entries
    linked = frappe.db.sql("""
        SELECT
            per.reference_name AS si_name,
            per.reference_doctype,
            pe.payment_type,
            COUNT(*) AS cnt,
            SUM(per.allocated_amount) AS allocated
        FROM `tabPayment Entry Reference` per
        JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE
            per.reference_doctype = 'Sales Invoice'
            AND per.reference_name IN %(si_names)s
            AND pe.docstatus = 1
        GROUP BY per.reference_name, per.reference_doctype, pe.payment_type
    """, {"si_names": si_names}, as_dict=True)

    # 4. Fetch linked Journal Entries
    je_linked = frappe.db.sql("""
        SELECT
            jea.reference_name AS si_name,
            COUNT(*) AS cnt,
            SUM(jea.credit_in_account_currency) AS je_credit
        FROM `tabJournal Entry Account` jea
        JOIN `tabJournal Entry` je ON je.name = jea.parent
        WHERE
            jea.reference_type = 'Sales Invoice'
            AND jea.reference_name IN %(si_names)s
            AND je.docstatus = 1
        GROUP BY jea.reference_name
    """, {"si_names": si_names}, as_dict=True)

    # Build lookup maps
    payment_map = {}
    for d in linked:
        payment_map.setdefault(d.si_name, []).append(d)
    je_map = {d.si_name: d for d in je_linked}

    # 5. Build result rows and summary
    results = []
    summary = {"total": 0, "negative": 0, "mismatch": 0, "both": 0, "ok": 0}

    for si in invoices:
        outstanding = flt(si.outstanding_amount, 2)
        gl_balance  = flt(gl_map.get(si.name, 0), 2)
        difference  = flt(outstanding - gl_balance, 2)

        cause, status = _classify(
            outstanding, gl_balance, difference,
            payment_map.get(si.name, []),
            je_map.get(si.name),
            si.grand_total,
        )

        results.append({
            "si_name":      si.name,
            "customer":     si.customer,
            "posting_date": str(si.posting_date),
            "grand_total":  flt(si.grand_total, 2),
            "outstanding":  outstanding,
            "gl_balance":   gl_balance,
            "difference":   difference,
            "status":       status,
            "cause":        cause,
            "debit_to":     si.debit_to,
            "company":      si.company,
        })

        summary["total"] += 1
        if status == "both":
            summary["both"]     += 1
            summary["negative"] += 1
            summary["mismatch"] += 1
        elif status == "negative":
            summary["negative"] += 1
        elif status == "mismatch":
            summary["mismatch"] += 1
        else:
            summary["ok"] += 1

    return {"results": results, "summary": summary}


def _classify(outstanding, gl_balance, difference, payments, je, grand_total):
    is_negative = outstanding < 0
    is_mismatch = abs(difference) > 0.5

    if not is_negative and not is_mismatch:
        return "", "ok"

    causes = []

    total_allocated = sum(flt(p.allocated) for p in payments)
    if total_allocated > flt(grand_total):
        causes.append("Excess payment applied (allocated {0} > invoice {1})".format(
            round(total_allocated, 2), round(grand_total, 2)))

    if je:
        causes.append("Journal Entry credit ({0} entries, total {1}) applied".format(
            je.cnt, round(flt(je.je_credit), 2)))

    if is_negative and abs(outstanding) < 1.0 and not causes:
        causes.append("Rounding difference (likely multi-currency reconciliation)")

    if len(payments) > 1:
        causes.append("Multiple payment entries linked ({0}) - possible duplicate allocation".format(
            len(payments)))

    if is_mismatch and not is_negative and not causes:
        causes.append("GL balance differs from SI outstanding - unposted or cancelled entry may exist")

    if not causes:
        if is_negative:
            causes.append("Outstanding is negative - check linked payments and credit notes")
        else:
            causes.append("Ledger mismatch - GL balance does not match SI outstanding")

    status = "both" if (is_negative and is_mismatch) else ("negative" if is_negative else "mismatch")
    return "; ".join(causes), status