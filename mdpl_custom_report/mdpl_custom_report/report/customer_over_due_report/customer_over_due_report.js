frappe.query_reports["Customer Over Due Report"] = {
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
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
        },
        {
            fieldname: "cost_center",
            label: __("Cost Center"),
            fieldtype: "MultiSelectList",
            options: "Cost Center",
            get_data: function (txt) {
                return frappe.db.get_link_options("Cost Center", txt);
            },
        },
        {
            fieldname: "apple_id",
            label: __("Apple ID"),
            fieldtype: "Check",
            default: 1,
            description: __(
                "Check to show only customers with Apple ID. Uncheck to show customers without Apple ID."
            ),
        },
        {
            fieldname: "overdue_days",
            label: __("Overdue Days"),
            fieldtype: "Int",
            default: 7,
            description: __(
                "Show only entries overdue for more than this number of days"
            ),
        },
    ],

    onload: function (report) {
        report.page.set_primary_action(__("Refresh"), function () {
            report.refresh();
        });
    },

    formatter: function (value, row, column, data, default_formatter) {
        // Capture raw numeric value before default_formatter converts it to
        // a formatted currency string like "Rs.1,200.00" which breaks > 0 check.
        var raw = value;

        value = default_formatter(value, row, column, data);

        if (column.fieldname.startsWith("daily_")) {
            if (raw > 0) {
                value = "<span style=\"color:red;font-weight:bold;\">" + value + "</span>";
            }
        }

        return value;
    },
};