frappe.query_reports["Sales Rep-wise per Store Productivity Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_end()
        },
        {
    	    	label: "Item Group",
    		fieldname: "item_group",
    		fieldtype: "MultiSelectList",
    		get_data: function (txt) {
        	return frappe.db.get_link_options("Item Group", txt);
    		}
	},
	{
    		label: "Parent Item Group",
    		fieldname: "parent_item_group",
    		fieldtype: "MultiSelectList",
    		get_data: function (txt) {
        	return frappe.db.get_link_options("Item Group", txt);
    		}
	},
        {
            "fieldname": "sales_rep",
            "label": __("Sales Rep"),
            "fieldtype": "Link",
            "options": "Sales Rep Info"
        }
    ]
};
