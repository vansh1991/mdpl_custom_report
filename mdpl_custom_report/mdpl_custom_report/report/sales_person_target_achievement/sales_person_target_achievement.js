frappe.query_reports["Sales Person Target Achievement"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "fiscal_year",
            label: __("Fiscal Year"),
            fieldtype: "Link",
            options: "Fiscal Year",
            reqd: 1,
            default: frappe.sys_defaults.fiscal_year,
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
            fieldname: "sales_person",
            label: __("Sales Person"),
            fieldtype: "Link",
            options: "Sales Person",
        },
        {
            fieldname: "item_group",
            label: __("Item Group"),
            fieldtype: "Link",
            options: "Item Group",
        },
        {
            fieldname: "show_zero_target",
            label: __("Show Rows With Zero Target"),
            fieldtype: "Check",
            default: 0,
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "achievement_pct") {
            var raw = data && data.achievement_pct;
            if (raw !== undefined && raw !== null) {
                if (raw >= 100) {
                    value = "<span style='color:green;font-weight:bold;'>" + value + "</span>";
                } else if (raw >= 75) {
                    value = "<span style='color:orange;font-weight:bold;'>" + value + "</span>";
                } else {
                    value = "<span style='color:red;font-weight:bold;'>" + value + "</span>";
                }
            }
        }

        if (column.fieldname === "variance" && data) {
            var raw_v = data.variance;
            if (raw_v < 0) {
                value = "<span style='color:red;'>" + value + "</span>";
            } else if (raw_v > 0) {
                value = "<span style='color:green;'>" + value + "</span>";
            }
        }

        return value;
    },

    onload: function (report) {
        report.page.set_primary_action(__("Refresh"), function () {
            report.refresh();
        });
    },
};