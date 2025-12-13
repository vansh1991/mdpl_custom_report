frappe.query_reports["sales invoice script report v2"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.now_date(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "default": frappe.datetime.now_date(),
            "reqd": 1
        },
        {
            "fieldname": "itm_group",
            "label": "Item Group",
            "fieldtype": "MultiSelectList",
            "options": "Item Group",
            "get_data": function(txt) {
                if (txt) return frappe.db.get_link_options("Item Group", txt);
                const allowed_parent_groups = ["Demo","Accessories","AirPods","Apple Watch","iPad","iPhone","Macbook"];
                return frappe.db.get_list('Item Group', {
                    fields: ["name"],
                    filters: { parent_item_group: ["in", allowed_parent_groups] }
                }).then(data => data.map(d => ({ value: d.name, label: d.name })));
            }
        },
        {
            "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "MultiSelectList",
            "options": "Customer",
            "get_data": function(txt) { return frappe.db.get_link_options("Customer", txt); }
        },
        {
            "fieldname": "parent_item_group",
            "label": "Parent Item Group",
            "fieldtype": "MultiSelectList",
            "options": "Item Group",
            "get_data": function(txt) {
                return frappe.db.get_list('Item Group', {
                    fields: ["name"],
                    filters: { is_group: 1, name: ["like", "%" + txt + "%"] },
                    limit: 20
                }).then(data => data.map(d => ({ value: d.name, label: d.name })));
            }
        },
        {
            "fieldname": "sales_rep",
            "label": "Sales Rep",
            "fieldtype": "Link",
            "options": "Sales Rep Info",
            "default": "",
        },
        {
            "fieldname": "apple_id",
            "label": "Apple Id",
            "fieldtype": "Check",
            "default": 1,
        }
    ]
}
