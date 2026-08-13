frappe.query_reports["Party Ledger vs Outstanding Reconciliation"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "party_type",
			"label": __("Party Type"),
			"fieldtype": "Select",
			"options": ["", "Customer", "Supplier"]
		},
		{
			"fieldname": "party",
			"label": __("Party"),
			"fieldtype": "Dynamic Link",
			"get_options": function () {
				let party_type = frappe.query_report.get_filter_value("party_type");
				return party_type || "Customer";
			}
		},
		{
			"fieldname": "to_date",
			"label": __("As On Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "show_difference_only",
			"label": __("Show Only Differences"),
			"fieldtype": "Check",
			"default": 1
		}
	]
};
