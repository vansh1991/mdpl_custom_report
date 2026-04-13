import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "party",              "label": _("Party"),                    "fieldtype": "Data",     "width": 180},
        {"fieldname": "party_type",         "label": _("Party Type"),               "fieldtype": "Data",     "width": 100},
        {"fieldname": "ledger_balance",     "label": _("Ledger Closing Balance"),   "fieldtype": "Currency", "width": 160},
        {"fieldname": "outstanding_amount", "label": _("Total Invoice Outstanding"), "fieldtype": "Currency", "width": 180},
        {"fieldname": "difference",         "label": _("Difference"),               "fieldtype": "Currency", "width": 130},
        {"fieldname": "status",             "label": _("Status"),                   "fieldtype": "Data",     "width": 120},
    ]


def get_data(filters):
    filters = filters or {}
    company   = filters.get("company")
    to_date   = filters.get("to_date")
    from_date = filters.get("from_date")
    gl_conditions = ["gle.docstatus < 2", "gle.party IS NOT NULL", "gle.party != ''"]
    if company:
        gl_conditions.append("gle.company = %(company)s")
    if from_date:
        gl_conditions.append("gle.posting_date >= %(from_date)s")
    if to_date:
        gl_conditions.append("gle.posting_date <= %(to_date)s")

    gl_query = f"""
        SELECT gle.party, gle.party_type,
               SUM(gle.debit - gle.credit) AS ledger_balance
        FROM `tabGL Entry` gle
        WHERE {' AND '.join(gl_conditions)}
        GROUP BY gle.party, gle.party_type
    """
    gl_data    = frappe.db.sql(gl_query, filters, as_dict=True)
    ledger_map = {(str(d.party), str(d.party_type)): d.ledger_balance or 0 for d in gl_data}
    si_conditions = ["si.docstatus = 1", "si.outstanding_amount > 0"]
    pi_conditions = ["pi.docstatus = 1", "pi.outstanding_amount > 0"]
    if company:
        si_conditions.append("si.company = %(company)s")
        pi_conditions.append("pi.company = %(company)s")
    if from_date:
        si_conditions.append("si.posting_date >= %(from_date)s")
        pi_conditions.append("pi.posting_date >= %(from_date)s")
    if to_date:
        si_conditions.append("si.posting_date <= %(to_date)s")
        pi_conditions.append("pi.posting_date <= %(to_date)s")

    inv_query = f"""
        SELECT si.customer AS party, 'Customer' AS party_type,
               SUM(si.outstanding_amount) AS outstanding_amount
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(si_conditions)}
        GROUP BY si.customer
        UNION ALL
        SELECT pi.supplier AS party, 'Supplier' AS party_type,
               SUM(pi.outstanding_amount) AS outstanding_amount
        FROM `tabPurchase Invoice` pi
        WHERE {' AND '.join(pi_conditions)}
        GROUP BY pi.supplier
    """
    inv_data        = frappe.db.sql(inv_query, filters, as_dict=True)
    outstanding_map = {}
    for d in inv_data:
        key = (str(d.party), str(d.party_type))
        outstanding_map[key] = outstanding_map.get(key, 0) + (d.outstanding_amount or 0)
    all_keys = set(ledger_map.keys()) | set(outstanding_map.keys())
    data = []
    for party, party_type in sorted(all_keys):
        ledger      = ledger_map.get((party, party_type), 0)
        outstanding = outstanding_map.get((party, party_type), 0)
        difference  = ledger - outstanding
        status      = "? Match" if abs(difference) < 0.01 else "? Difference"
        data.append({
            "party":              party,
            "party_type":         party_type,
            "ledger_balance":     ledger,
            "outstanding_amount": outstanding,
            "difference":         difference,
            "status":             status,
        })
    party_type_filter = filters.get("party_type")
    if party_type_filter:
        data = [r for r in data if r["party_type"] == party_type_filter]
    if filters.get("show_diff_only"):
        data = [r for r in data if abs(r["difference"]) >= 0.01]
    return data