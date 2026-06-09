import frappe
from frappe import _
from frappe.utils import flt, date_diff, today


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data, summary = get_data(filters)
	return columns, data, None, None, summary


def get_columns():
	return [
		{
			"label": _("Invoice / Voucher"),
			"fieldname": "invoice",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 180,
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 0,
			"hidden": 1,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 105,
		},
		{
			"label": _("Due Date"),
			"fieldname": "due_date",
			"fieldtype": "Date",
			"width": 105,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Invoiced Amount"),
			"fieldname": "invoiced_amount",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Credit Note"),
			"fieldname": "credit_note",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Linked JV Adj."),
			"fieldname": "linked_jv_amount",
			"fieldtype": "Currency",
			"width": 135,
		},
		{
			"label": _("Unlinked JV Adj."),
			"fieldname": "unlinked_jv_amount",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Outstanding (AR)"),
			"fieldname": "ar_outstanding",
			"fieldtype": "Currency",
			"width": 145,
		},
		{
			"label": _("Outstanding (with JV)"),
			"fieldname": "outstanding_with_jv",
			"fieldtype": "Currency",
			"width": 165,
		},
		{
			"label": _("GL Balance"),
			"fieldname": "gl_balance",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Difference"),
			"fieldname": "difference",
			"fieldtype": "Currency",
			"width": 115,
		},
		{
			"label": _("Age (Days)"),
			"fieldname": "age_days",
			"fieldtype": "Int",
			"width": 95,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def get_data(filters):
	company         = filters.get("company")
	party           = filters.get("party")
	from_date       = filters.get("from_date")
	to_date         = filters.get("to_date")
	ageing_based_on = filters.get("ageing_based_on") or "Due Date"

	# ── 1. Invoice conditions ─────────────────────────────────────────────────
	conditions = ["si.docstatus = 1", "si.is_return = 0"]
	values: list = []

	if company:
		conditions.append("si.company = %s")
		values.append(company)
	if party:
		conditions.append("si.customer = %s")
		values.append(party)
	if from_date:
		conditions.append("si.posting_date >= %s")
		values.append(from_date)
	if to_date:
		conditions.append("si.posting_date <= %s")
		values.append(to_date)

	where = " AND ".join(conditions)

	# ── 2. Fetch invoices ─────────────────────────────────────────────────────
	invoices = frappe.db.sql(
		f"""
		SELECT
			si.name               AS invoice,
			si.posting_date,
			si.due_date,
			si.customer,
			si.company,
			si.grand_total        AS invoiced_amount,
			si.outstanding_amount AS ar_outstanding
		FROM `tabSales Invoice` si
		WHERE {where}
		ORDER BY si.posting_date ASC
		""",
		values,
		as_dict=True,
	)

	if not invoices:
		return [], []

	invoice_names = [d.invoice for d in invoices]
	ph = ", ".join(["%s"] * len(invoice_names))

	# ── 3. Paid amounts via Payment Entry ─────────────────────────────────────
	paid_map = {}
	for row in frappe.db.sql(
		f"""
		SELECT per.reference_name AS invoice,
		       SUM(per.allocated_amount) AS paid
		FROM `tabPayment Entry Reference` per
		JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE per.reference_doctype = 'Sales Invoice'
		  AND per.reference_name IN ({ph})
		  AND pe.docstatus = 1
		GROUP BY per.reference_name
		""",
		tuple(invoice_names),
		as_dict=True,
	):
		paid_map[row.invoice] = flt(row.paid)

	# ── 4. Credit notes ───────────────────────────────────────────────────────
	cn_map = {}
	for row in frappe.db.sql(
		f"""
		SELECT si.return_against AS invoice,
		       SUM(ABS(si.grand_total)) AS cn_amount
		FROM `tabSales Invoice` si
		WHERE si.docstatus = 1
		  AND si.is_return = 1
		  AND si.return_against IN ({ph})
		GROUP BY si.return_against
		""",
		tuple(invoice_names),
		as_dict=True,
	):
		cn_map[row.invoice] = flt(row.cn_amount)

	# ── 5. JVs explicitly linked to invoices (reference_type = Sales Invoice) ─
	linked_jv_map = {}
	for row in frappe.db.sql(
		f"""
		SELECT jea.reference_name AS invoice,
		       SUM(jea.debit_in_account_currency
		         - jea.credit_in_account_currency) AS jv_net
		FROM `tabJournal Entry Account` jea
		JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE jea.reference_type  = 'Sales Invoice'
		  AND jea.reference_name  IN ({ph})
		  AND jea.party_type      = 'Customer'
		  AND je.docstatus        = 1
		GROUP BY jea.reference_name
		""",
		tuple(invoice_names),
		as_dict=True,
	):
		linked_jv_map[row.invoice] = flt(row.jv_net)

	# ── 6. GL balance per invoice (all vouchers tagged to that invoice) ────────
	gl_map = {}
	for row in frappe.db.sql(
		f"""
		SELECT gle.against_voucher AS invoice,
		       SUM(gle.debit - gle.credit) AS gl_bal
		FROM `tabGL Entry` gle
		WHERE gle.against_voucher_type = 'Sales Invoice'
		  AND gle.against_voucher      IN ({ph})
		  AND gle.party_type           = 'Customer'
		  AND gle.is_cancelled         = 0
		GROUP BY gle.against_voucher
		""",
		tuple(invoice_names),
		as_dict=True,
	):
		gl_map[row.invoice] = flt(row.gl_bal)

	# ── 7. Unlinked JVs — party level, NO invoice reference ──────────────────
	#    Fetch once per unique (party, company) combination visible in the result
	parties   = list({d.customer for d in invoices})
	companies = list({d.company  for d in invoices})

	party_ph   = ", ".join(["%s"] * len(parties))
	company_ph = ", ".join(["%s"] * len(companies))

	unlinked_jv_rows = frappe.db.sql(
		f"""
		SELECT
			jea.party                           AS customer,
			je.company,
			SUM(jea.debit_in_account_currency
			  - jea.credit_in_account_currency) AS jv_net,
			COUNT(DISTINCT je.name)             AS jv_count
		FROM `tabJournal Entry Account` jea
		JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE jea.party_type  = 'Customer'
		  AND jea.party       IN ({party_ph})
		  AND je.company      IN ({company_ph})
		  AND je.docstatus    = 1
		  AND (jea.reference_type IS NULL OR jea.reference_type = '')
		GROUP BY jea.party, je.company
		""",
		tuple(parties) + tuple(companies),
		as_dict=True,
	)

	# Build a dict keyed by (customer, company)
	unlinked_jv_map = {}
	for row in unlinked_jv_rows:
		unlinked_jv_map[(row.customer, row.company)] = {
			"jv_net":   flt(row.jv_net),
			"jv_count": row.jv_count,
		}

	# ── 8. Distribute unlinked JVs proportionally across open invoices ────────
	#    Weight = ar_outstanding of each invoice / total ar_outstanding per party
	from collections import defaultdict
	party_ar_total = defaultdict(float)
	for inv in invoices:
		party_ar_total[(inv.customer, inv.company)] += flt(inv.ar_outstanding)

	# ── 9. Build rows ─────────────────────────────────────────────────────────
	data = []
	total_invoiced = total_paid = total_cn = 0
	total_linked_jv = total_unlinked_jv = 0
	total_ar = total_with_jv = total_gl = total_diff = 0

	for inv in invoices:
		name           = inv.invoice
		invoiced       = flt(inv.invoiced_amount)
		ar_outstanding = flt(inv.ar_outstanding)
		paid           = paid_map.get(name, 0)
		credit_note    = cn_map.get(name, 0)
		linked_jv      = linked_jv_map.get(name, 0)
		gl_balance     = gl_map.get(name, 0)

		# Proportional share of unlinked JVs for this party
		key            = (inv.customer, inv.company)
		party_total_ar = party_ar_total.get(key, 0)
		unlinked_info  = unlinked_jv_map.get(key, {})
		unlinked_total = unlinked_info.get("jv_net", 0)

		if party_total_ar:
			unlinked_jv = flt(
				unlinked_total * (ar_outstanding / party_total_ar), 2
			)
		else:
			unlinked_jv = 0

		# Outstanding = Invoice - Paid - CN + Linked JV + Unlinked JV (proportional)
		outstanding_with_jv = flt(
			invoiced - paid - credit_note + linked_jv + unlinked_jv, 2
		)
		difference = flt(outstanding_with_jv - gl_balance, 2)

		age_date = inv.due_date if ageing_based_on == "Due Date" else inv.posting_date
		age_days = date_diff(today(), age_date) if age_date else 0

		if outstanding_with_jv <= 0:
			status = "Paid"
		elif flt(paid + credit_note) > 0 or unlinked_jv or linked_jv:
			status = "Partly Paid"
		else:
			status = "Unpaid"

		# Accumulate totals
		total_invoiced    += invoiced
		total_paid        += paid
		total_cn          += credit_note
		total_linked_jv   += linked_jv
		total_unlinked_jv += unlinked_jv
		total_ar          += ar_outstanding
		total_with_jv     += outstanding_with_jv
		total_gl          += gl_balance
		total_diff        += difference

		data.append({
			"invoice":            name,
			"voucher_type":       "Sales Invoice",
			"posting_date":       inv.posting_date,
			"due_date":           inv.due_date,
			"customer":           inv.customer,
			"invoiced_amount":    invoiced,
			"paid_amount":        paid,
			"credit_note":        credit_note,
			"linked_jv_amount":   linked_jv,
			"unlinked_jv_amount": unlinked_jv,
			"ar_outstanding":     ar_outstanding,
			"outstanding_with_jv": outstanding_with_jv,
			"gl_balance":         gl_balance,
			"difference":         difference,
			"age_days":           age_days,
			"status":             status,
		})

	# ── 10. Unlinked JV summary rows (one per party) ──────────────────────────
	#     Show a separate section at the bottom with raw JV totals for audit
	if unlinked_jv_rows:
		data.append({
			"invoice":            "── Unlinked JV Summary ──",
			"voucher_type":       "",
			"posting_date":       None,
			"due_date":           None,
			"customer":           "",
			"invoiced_amount":    None,
			"paid_amount":        None,
			"credit_note":        None,
			"linked_jv_amount":   None,
			"unlinked_jv_amount": None,
			"ar_outstanding":     None,
			"outstanding_with_jv": None,
			"gl_balance":         None,
			"difference":         None,
			"age_days":           None,
			"status":             "",
		})
		for row in unlinked_jv_rows:
			data.append({
				"invoice":            f"{row.jv_count} Journal Entries",
				"voucher_type":       "Journal Entry",
				"posting_date":       None,
				"due_date":           None,
				"customer":           row.customer,
				"invoiced_amount":    None,
				"paid_amount":        None,
				"credit_note":        None,
				"linked_jv_amount":   None,
				"unlinked_jv_amount": flt(row.jv_net),
				"ar_outstanding":     None,
				"outstanding_with_jv": None,
				"gl_balance":         None,
				"difference":         None,
				"age_days":           None,
				"status":             "Unlinked JV",
			})

	# ── 11. Summary cards ─────────────────────────────────────────────────────
	currency = frappe.defaults.get_user_default("currency")
	summary = [
		{
			"label":    _("Total Invoiced"),
			"value":    total_invoiced,
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":    _("Total Paid"),
			"value":    total_paid,
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":    _("AR Outstanding"),
			"value":    total_ar,
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":    _("Unlinked JV Total"),
			"value":    sum(r.get("jv_net", 0) for r in unlinked_jv_rows),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":    _("Outstanding (with JV)"),
			"value":    total_with_jv,
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":    _("GL Balance"),
			"value":    total_gl,
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"label":     _("Net Difference"),
			"value":     flt(total_diff, 2),
			"datatype":  "Currency",
			"currency":  currency,
			"indicator": "Green" if abs(flt(total_diff, 2)) < 1 else "Red",
		},
	]

	return data, summary
