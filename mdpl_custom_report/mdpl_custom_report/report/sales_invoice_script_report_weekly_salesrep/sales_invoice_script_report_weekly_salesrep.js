frappe.query_reports["Sales Invoice Script Report Weekly SalesRep"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_end()
        },
        {
            "fieldname": "itm_group",
            "label": "Item Group",
            "fieldtype": "MultiSelectList",
            "options": "Item Group",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Item Group", txt);
            }
        },
        {
            "fieldname": "parent_item_group",
            "label": "Parent Item Group",
            "fieldtype": "MultiSelectList",
            "options": "Item Group",
            "get_data": function(txt) {
                return frappe.db.get_list('Item Group', {
                    fields: ["name"],
                    filters: { is_group: 1 }
                }).then(data => data.map(d => ({ value: d.name, label: d.name })));
            }
        },
        {
            "fieldname": "sales_rep",
            "label": "Sales Rep",
            "fieldtype": "Link",
            "options": "Sales Rep Info"
        }
    ]
};
