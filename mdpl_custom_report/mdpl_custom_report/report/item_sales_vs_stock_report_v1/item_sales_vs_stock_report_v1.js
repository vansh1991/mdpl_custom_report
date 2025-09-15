// Copyright (c) 2025, TechDude and contributors
// For license information, please see license.txt

frappe.query_reports["item sales vs stock report v1"] = {
	"filters": [
{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"reqd": 1
		},
		{
            		"fieldname": "parent_item_group",
            		"label": __("Parent Item Group"),
            		"fieldtype": "Link",
            	"options": "Item Group"
        	},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "MultiSelectList",
			options: "Item Group",
			get_data: function (txt) {
				return frappe.db.get_link_options("Item Group");
			},
		},
		{
			"fieldname": "warehouse",
			"label": "Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse"
		},
		{
            		"fieldname": "apple_id",
            		"label": __("Apple ID"),
            		"fieldtype": "Check",
            		"default": 1
        	}
	]
};
