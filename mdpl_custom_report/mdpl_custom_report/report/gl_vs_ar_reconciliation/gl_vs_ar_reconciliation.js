// Copyright (c) 2024, Mahesh Distributor Pvt Ltd
// License: MIT

frappe.query_reports["GL vs AR Reconciliation"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            reqd: 1
        },
        {
            fieldname: "report_date",
            label: __("Report Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "status") {
            if (value && value.includes("✅")) {
                value = "<span style='color: green; font-weight: bold;'>" + value + "</span>";
            } else if (value && value.includes("⚠️")) {
                value = "<span style='color: orange; font-weight: bold;'>" + value + "</span>";
            }
        }

        if (column.fieldname === "difference") {
            if (data && Math.abs(data.difference) < 1) {
                value = "<span style='color: green; font-weight: bold;'>" + value + "</span>";
            } else if (data && Math.abs(data.difference) >= 1) {
                value = "<span style='color: red; font-weight: bold;'>" + value + "</span>";
            }
        }

        if (column.fieldname === "gl_balance") {
            if (data && data.gl_balance < 0) {
                value = "<span style='color: blue;'>" + value + "</span>";
            }
        }

        return value;
    }
};
