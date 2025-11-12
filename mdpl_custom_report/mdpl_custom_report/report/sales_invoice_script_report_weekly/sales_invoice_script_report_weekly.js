// Copyright (c) 2025, TechDude and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Invoice Script Report Weekly"] = {
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
            // If there is search text, use frappe.db.get_link_options to get the results
            if (txt) {
               return frappe.db.get_link_options("Item Group", txt);
            }

            // Otherwise, return the static filtered data based on allowed parent item groups
            const allowed_parent_groups = [
               "Demo", "Accessories", "AirPods", "Apple Watch", "iPad", "iPhone", "Macbook"
             ];

           // Fetch child item groups based on the allowed parent groups
           return frappe.db.get_list('Item Group', {
              fields: ["name"],
              filters: {
                parent_item_group: ["in", allowed_parent_groups]
               }
             }).then(data => {
            // Return all the filtered item groups when no search text is provided
            return data.map(d => ({ value: d.name, label: d.name }));
           });
         }
       },
           
       {
            "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "MultiSelectList",
            "options": "Customer",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Customer", txt);
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
            	filters: {
                is_group: 1,
                name: ["like", "%" + txt + "%"]
            	},
            	limit: 20
        	}).then(data => {
            	return data.map(d => ({
                	value: d.name,
                	label: d.name
            	}));
        	});
    	}
	},
    {
	"fieldname": "sales_rep",
	"label": "Sales Rep",
	"fieldtype": "MultiSelectList",
	"options": "Sales Rep Info",
	"default": "",
    },

    {
        "fieldname": "apple_id",
        "label": "Apple Id",
        "fieldtype": "Check",
        "default": 1,
    
    }, 
    ]
};
