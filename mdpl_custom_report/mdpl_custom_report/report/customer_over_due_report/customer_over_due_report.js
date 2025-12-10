frappe.query_reports["Customer Over Due Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "cost_center",
            "label": __("Cost Center"),
            "fieldtype": "Link",
            "options": "Cost Center"
        },
	{
            "fieldname": "apple_id",
            "label": __("Apple ID"),
            "fieldtype": "Check",
            "default": 1,
            "description": __("Check to show only customers with Apple ID. Uncheck to show customers without Apple ID.")
        }
    ],

    onload: function(report) {
        report.page.set_primary_action(__('Refresh'), function() {
            report.refresh();
        });
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname.startsWith('daily_') || column.fieldname.startsWith('weekly_')) {
            if (value > 0) {
                value = `<span style="color:red;font-weight:bold;">${value}</span>`;
            }
        }
        return value;
    }
};
