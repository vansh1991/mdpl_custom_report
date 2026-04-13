frappe.query_reports["Ledger vs Outstanding"] = {
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
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "party_type",
            label: __("Party Type"),
            fieldtype: "Select",
            options: "\nCustomer\nSupplier"
        },
        {
            fieldname: "show_diff_only",
            label: __("Show Differences Only"),
            fieldtype: "Check",
            default: 0
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "difference" && data) {
            if (Math.abs(data.difference) >= 0.01) {
                value = `<span style="color:red;font-weight:500;">${value}</span>`;
            }
        }

        if (column.fieldname === "status" && data) {
            if (data.status === "? Match") {
                value = `<span style="color:green;">${value}</span>`;
            } else {
                value = `<span style="color:red;">${value}</span>`;
            }
        }

        return value;
    }
};