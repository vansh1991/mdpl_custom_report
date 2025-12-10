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
    ],

    onload: function(report) {
        // Hide serial number column completely
        report.show_serial_number = false;

        report.refresh = function() {
            frappe.query_report.__proto__.refresh.call(this);

            setTimeout(() => {
                if (this.datatable && this.datatable.wrapper) {
                    // Remove serial number column
                    const first_col = this.datatable.wrapper.querySelector(".dt-header .dt-cell");
                    if (first_col && first_col.innerText === "#") first_col.remove();

                    // Apply dynamic freeze to both columns and headers
                    apply_dynamic_freeze(this.datatable);
                }
            }, 500);
        };
    }
};

function apply_dynamic_freeze(datatable) {
    if (!datatable) return;

    const wrapper = datatable.wrapper;
    const header_cells = wrapper.querySelectorAll(".dt-header .dt-cell");
    let leftOffset = 0;

    // Remove old styles if exist
    const oldStyle = document.getElementById("freeze-column-style");
    if (oldStyle) oldStyle.remove();

    const style = document.createElement("style");
    style.id = "freeze-column-style";
    let css = "";

    // Freeze first 4 columns dynamically
    for (let i = 0; i < 6 && i < header_cells.length; i++) {
        const width = header_cells[i].offsetWidth;

        css += `
            .dt-cell:nth-child(${i + 1}),
            .dt-header .dt-cell:nth-child(${i + 1}) {
                position: sticky !important;
                left: ${leftOffset}px !important;
                background: var(--background-color, #fff) !important;
                color: var(--text-color, #000) !important;
                border-right: 1px solid var(--border-color, #ccc) !important;
                z-index: 10 !important;
            }

            .dt-header .dt-cell:nth-child(${i + 1}) {
                top: 0 !important;
                z-index: 20 !important; /* Higher than data cells */
            }
        `;

        leftOffset += width;
    }

    // Freeze header row
    css += `
        .dt-header {
            position: sticky !important;
            top: 0 !important;
            background: var(--background-color, #fff) !important;
            z-index: 15 !important;
        }
    `;

    style.innerHTML = css;
    document.head.appendChild(style);
}
