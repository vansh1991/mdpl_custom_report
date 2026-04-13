# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, nowdate, now


@frappe.whitelist()
def get_si_investigation(si_name):
    if not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc("Sales Invoice", si_name)

    gl_entries = frappe.db.sql("""
        SELECT
            account, party_type, party,
            debit, credit,
            debit - credit AS net,
            remarks, against_voucher, against_voucher_type,
            cost_center, posting_date
        FROM `tabGL Entry`
        WHERE voucher_type = 'Sales Invoice'
          AND voucher_no   = %(si)s
          AND is_cancelled = 0
        ORDER BY account
    """, {"si": si_name}, as_dict=True)

    payment_entries = frappe.db.sql("""
        SELECT
            pe.name, pe.posting_date, pe.payment_type,
            pe.paid_amount, pe.received_amount,
            per.allocated_amount, pe.remarks
        FROM `tabPayment Entry Reference` per
        JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE per.reference_doctype = 'Sales Invoice'
          AND per.reference_name    = %(si)s
          AND pe.docstatus          = 1
        ORDER BY pe.posting_date
    """, {"si": si_name}, as_dict=True)

    journal_entries = frappe.db.sql("""
        SELECT
            je.name, je.posting_date, je.voucher_type,
            jea.account, jea.debit_in_account_currency,
            jea.credit_in_account_currency, je.user_remark
        FROM `tabJournal Entry Account` jea
        JOIN `tabJournal Entry` je ON je.name = jea.parent
        WHERE jea.reference_type = 'Sales Invoice'
          AND jea.reference_name = %(si)s
          AND je.docstatus        = 1
        ORDER BY je.posting_date
    """, {"si": si_name}, as_dict=True)

    credit_notes = frappe.db.sql("""
        SELECT
            si.name, si.posting_date, si.grand_total,
            si.outstanding_amount, si.is_return,
            si.return_against
        FROM `tabSales Invoice` si
        WHERE si.return_against = %(si)s
          AND si.docstatus       = 1
    """, {"si": si_name}, as_dict=True)

    receivable_balance = frappe.db.sql("""
        SELECT SUM(debit) - SUM(credit) AS balance
        FROM `tabGL Entry`
        WHERE voucher_type = 'Sales Invoice'
          AND voucher_no   = %(si)s
          AND account      = %(account)s
          AND is_cancelled = 0
    """, {"si": si_name, "account": doc.debit_to}, as_dict=True)

    gl_balance = flt(receivable_balance[0].balance if receivable_balance else 0, 2)

    # Fetch available accounts for same-account JE option
    write_off_account = frappe.db.get_value("Company", doc.company, "write_off_account") or ""

    return {
        "si_name":          doc.name,
        "customer":         doc.customer,
        "posting_date":     str(doc.posting_date),
        "grand_total":      flt(doc.grand_total, 2),
        "outstanding":      flt(doc.outstanding_amount, 2),
        "is_return":        doc.is_return,
        "return_against":   doc.return_against or "",
        "debit_to":         doc.debit_to,
        "company":          doc.company,
        "cost_center":      doc.cost_center or "",
        "gl_balance":       gl_balance,
        "difference":       flt(doc.outstanding_amount - gl_balance, 2),
        "gl_entries":       gl_entries,
        "payment_entries":  payment_entries,
        "journal_entries":  journal_entries,
        "credit_notes":     credit_notes,
        "status":           doc.status,
        "write_off_account": write_off_account,
    }


@frappe.whitelist()
def get_accounts_for_company(company):
    """Return expense/income/receivable accounts for the JE second leg dropdown."""
    accounts = frappe.db.sql("""
        SELECT name, account_type, root_type
        FROM `tabAccount`
        WHERE company    = %(company)s
          AND is_group   = 0
          AND disabled   = 0
          AND root_type  IN ('Income', 'Expense', 'Asset', 'Liability')
        ORDER BY root_type, name
        LIMIT 300
    """, {"company": company}, as_dict=True)
    return accounts


@frappe.whitelist()
def create_offset_je(si_name, posting_date, remarks, je_mode="writeoff", second_account=None):
    """
    je_mode:
        'writeoff'   - Debtors <-> Write Off account (default)
        'same'       - Debtors debit AND Debtors credit (self-offsetting, no party on credit leg)
        'custom'     - Debtors <-> second_account (user picks the account)
    """
    if not frappe.has_permission("Journal Entry", "create"):
        frappe.throw(_("Not permitted to create Journal Entry"), frappe.PermissionError)

    doc = frappe.get_doc("Sales Invoice", si_name)

    if doc.docstatus != 1:
        frappe.throw(_("Sales Invoice must be submitted"))

    outstanding = flt(doc.outstanding_amount, 2)
    if outstanding == 0:
        return {"status": "skipped", "message": "Outstanding is already zero. No JE needed."}

    cost_center = doc.cost_center or _get_default_cost_center(doc.company)
    amount = abs(outstanding)

    if je_mode == "same":
        # Both legs use the Debtors account
        # Debit leg has party (to link to SI), credit leg has no party
        if outstanding < 0:
            # Outstanding is negative: debit Debtors (with party) to bring to zero
            # credit Debtors (without party) to balance
            accounts = [
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "cost_center":                cost_center,
                },
            ]
        else:
            # Outstanding is positive but GL is wrong
            accounts = [
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "cost_center":                cost_center,
                },
            ]

    elif je_mode == "custom":
        if not second_account:
            frappe.throw(_("Please select a second account for the JE."))
        if outstanding < 0:
            accounts = [
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    second_account,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "cost_center":                cost_center,
                },
            ]
        else:
            accounts = [
                {
                    "account":                    second_account,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
            ]

    else:
        # Default: writeoff mode
        write_off_account = _get_write_off_account(doc.company)
        if outstanding < 0:
            accounts = [
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    write_off_account,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "cost_center":                cost_center,
                },
            ]
        else:
            accounts = [
                {
                    "account":                    write_off_account,
                    "debit_in_account_currency":  amount,
                    "credit_in_account_currency": 0,
                    "cost_center":                cost_center,
                },
                {
                    "account":                    doc.debit_to,
                    "party_type":                 "Customer",
                    "party":                      doc.customer,
                    "debit_in_account_currency":  0,
                    "credit_in_account_currency": amount,
                    "reference_type":             "Sales Invoice",
                    "reference_name":             si_name,
                    "cost_center":                cost_center,
                },
            ]

    je = frappe.get_doc({
        "doctype":      "Journal Entry",
        "voucher_type": "Journal Entry",
        "posting_date": posting_date or nowdate(),
        "company":      doc.company,
        "user_remark":  remarks or "Offsetting JE to zero out outstanding on {0}".format(si_name),
        "accounts":     accounts,
    })
    je.insert(ignore_permissions=False)
    je.submit()

    frappe.get_doc({
        "doctype":           "Comment",
        "comment_type":      "Info",
        "reference_doctype": "Sales Invoice",
        "reference_name":    si_name,
        "content": "Offsetting Journal Entry <b>{0}</b> ({1} mode) created by {2} to zero out outstanding of {3}.".format(
            je.name, je_mode, frappe.session.user, outstanding),
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status":  "success",
        "je_name": je.name,
        "message": "Journal Entry {0} created and submitted successfully.".format(je.name),
    }


def _get_write_off_account(company):
    write_off = frappe.db.get_value("Company", company, "write_off_account")
    if write_off:
        return write_off
    fallback = frappe.db.get_value("Account", {
        "company": company, "account_name": ["like", "%Write%Off%"], "is_group": 0,
    }, "name")
    if fallback:
        return fallback
    last = frappe.db.get_value("Account", {
        "company": company, "root_type": "Income", "is_group": 0, "disabled": 0,
    }, "name")
    if last:
        return last
    frappe.throw(_("Could not find a write-off account for company {0}. Set it in Company settings.").format(company))


def _get_default_cost_center(company):
    return frappe.db.get_value("Company", company, "cost_center") or ""