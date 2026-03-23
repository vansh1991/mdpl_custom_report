// Copyright (c) 2025, TechDude and contributors
// For license information, please see license.txt
frappe.query_reports["Customer Ledger Summary Updated v1"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "party",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			on_change: () => {
				var party = frappe.query_report.get_filter_value("party");
				if (party) {
					frappe.db.get_value("Customer", party, ["tax_id", "customer_name"], function (value) {
						frappe.query_report.set_filter_value("tax_id", value["tax_id"]);
						frappe.query_report.set_filter_value("customer_name", value["customer_name"]);
					});
				} else {
					frappe.query_report.set_filter_value("tax_id", "");
					frappe.query_report.set_filter_value("customer_name", "");
				}
			},
		},
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		{
			fieldname: "payment_terms_template",
			label: __("Payment Terms Template"),
			fieldtype: "Link",
			options: "Payment Terms Template",
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname: "sales_partner",
			label: __("Sales Partner"),
			fieldtype: "Link",
			options: "Sales Partner",
		},
		{
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Rep Info",
		},
		{
			fieldname: "tax_id",
			label: __("Tax Id"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			fieldname: "customer_name",
			label: __("Customer Name"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			label: __("Apple ID"),
			fieldname: "apple_id",
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "avg_outstanding_ranges",
			label: __("Average Outstanding"),
			fieldtype: "Data",
			default: "10, 15",
		},

		// -- NEW FILTER: GST No search --------------------------------------
		{
			fieldname: "gstin",
			label: __("GST No (GSTIN)"),
			fieldtype: "Data",
			description: __("Filter by GST number - shows all customers sharing this GST No"),
			on_change: () => {
				// When a GSTIN is typed, auto-enable group_by_gst for convenience
				const gstin = frappe.query_report.get_filter_value("gstin");
				if (gstin) {
					frappe.query_report.set_filter_value("group_by_gst", 1);
				}
			},
		},
		// -- NEW FILTER: Group by GST No toggle ----------------------------
		{
			fieldname: "group_by_gst",
			label: __("Group by GST No"),
			fieldtype: "Check",
			default: 0,
			description: __(
				"Consolidate customers sharing the same GST number into a single row"
			),
			on_change: () => {
				// Refresh immediately when toggled so the report re-runs
				frappe.query_report.refresh();
			},
		},
		// -- END NEW --------------------------------------------------------
	],
};