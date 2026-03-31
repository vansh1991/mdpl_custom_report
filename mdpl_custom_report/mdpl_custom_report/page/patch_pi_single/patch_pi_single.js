frappe.pages["patch-pi-single"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Patch Purchase Invoice Fields",
        single_column: true,
    });
    new PatchPISingle(page, wrapper);
};

var PIS2_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_pi_single.patch_pi_single.";

var PatchPISingle = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.pi_data = null;
        this.posting_date_ctrl = null;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".pis2-wrap { max-width: 1160px; margin: 24px auto; padding: 0 16px; }" +
            ".pis2-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 20px; }" +
            ".pis2-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".pis2-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".pis2-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 14px; }" +
            ".pis2-meta { display: flex; gap: 32px; flex-wrap: wrap; margin-bottom: 8px; }" +
            ".pis2-meta-item { display: flex; flex-direction: column; gap: 2px; }" +
            ".pis2-meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; }" +
            ".pis2-meta-value { font-size: 14px; font-weight: 500; color: var(--text-color); }" +
            ".pis2-patch-row { display: flex; gap: 24px; align-items: flex-end; flex-wrap: wrap;" +
            "  padding: 16px 0 8px; border-top: 1px solid var(--border-color); margin-top: 12px; }" +
            ".pis2-patch-field { display: flex; flex-direction: column; gap: 4px; min-width: 220px; }" +
            ".pis2-patch-field label { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; }" +
            ".pis2-date-warning { font-size: 11px; color: var(--text-muted); margin-top: 4px; }" +
            ".pis2-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".pis2-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".pis2-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".pis2-table tr:last-child td { border-bottom: none; }" +
            ".pis2-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".pis2-table .link-btn { display: none !important; }" +
            ".pis2-changes { margin-top: 12px; padding: 12px 16px;" +
            "  background: var(--alert-bg-success); border: 1px solid var(--alert-border-success);" +
            "  border-radius: var(--border-radius); font-size: 12px; color: var(--alert-text-success); }" +
            ".pis2-changes ul { margin: 6px 0 0 16px; }" +
            ".pis2-warn-badge { display: inline-block; background: var(--yellow-100);" +
            "  color: var(--yellow-700, #854d0e); border-radius: 4px; font-size: 10px;" +
            "  padding: 1px 6px; margin-left: 6px; font-weight: 600; vertical-align: middle; }"
        );

        this.$wrap = $('<div class="pis2-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        // -- Search row --
        var $search = $('<div class="pis2-search-row"></div>').appendTo(this.$wrap);
        this.pi_field = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "purchase_invoice",
                options: "Purchase Invoice", label: "Purchase Invoice",
                filters: { docstatus: 1 },
                placeholder: "Search submitted purchase invoice...",
            },
            parent: $search, render_input: true,
        });
        this.pi_field.refresh();

        $('<button class="btn btn-primary btn-sm" style="height:32px;white-space:nowrap">Load PI</button>')
            .appendTo($search).on("click", function () { me.load_pi(); });
        $(this.pi_field.input).on("keydown", function (e) { if (e.which === 13) me.load_pi(); });

        this.$info       = $('<div class="pis2-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$items_card = $('<div class="pis2-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$save_row   = $('<div style="display:none;margin-bottom:32px;"></div>').appendTo(this.$wrap);
        $('<button class="btn btn-primary">Save Changes</button>')
            .appendTo(this.$save_row).on("click", function () { me.save_changes(); });
        this.$result = $('<div></div>').appendTo(this.$wrap);
    },

    load_pi: function () {
        var me = this;
        var pi = (this.pi_field.get_value() || "").trim();
        if (!pi) { frappe.msgprint(__("Please enter a Purchase Invoice name.")); return; }

        frappe.call({
            method: PIS2_METHOD_BASE + "get_pi_details",
            args: { pi_name: pi },
            freeze: true, freeze_message: __("Loading purchase invoice..."),
            callback: function (r) {
                if (r.message) { me.pi_data = r.message; me.render(r.message); }
            },
        });
    },

    render: function (data) {
        var me = this;

        // -- Header info card --
        this.$info.empty().show().append(
            '<div class="pis2-card-title">Purchase Invoice Details</div>' +
            '<div class="pis2-meta">' +
            me._meta("Purchase Invoice", data.pi_name) +
            me._meta("Supplier", data.supplier) +
            me._meta("Date", data.posting_date) +
            me._meta("Grand Total", format_currency(data.grand_total)) +
            me._meta("Status", data.status) +
            "</div>" +

            // -- Posting Date patch section --
            '<div class="pis2-patch-row">' +
            '<div class="pis2-patch-field">' +
            '<label>Change Posting Date <span class="pis2-warn-badge">? Updates GL Entries</span></label>' +
            '<div id="pis2-posting-date-wrap"></div>' +
            '<div class="pis2-date-warning">Changing the posting date will update the posting date on all linked GL entries and Payment Ledger entries for this invoice.</div>' +
            '</div>' +
            '</div>'
        );

        // Build the Date control after DOM is in place
        this.posting_date_ctrl = frappe.ui.form.make_control({
            df: {
                fieldtype: "Date",
                fieldname: "new_posting_date",
                label: "",
                placeholder: "Leave blank to keep current date",
            },
            parent: this.$info.find("#pis2-posting-date-wrap"),
            render_input: true,
        });
        this.posting_date_ctrl.set_value("");
        this.posting_date_ctrl.refresh();

        // -- Items table --
        this.$items_card.empty().show().append('<div class="pis2-card-title">Items</div>');
        var $itbl = $(
            '<table class="pis2-table"><thead><tr>' +
            "<th>#</th><th>Item Code</th><th>Item Name</th><th>Qty</th><th>Rate</th>" +
            "<th style='min-width:180px'>Item Group</th>" +
            "<th style='min-width:200px'>Expense Account <span class='pis2-warn-badge'>? Updates GL</span></th>" +
            "<th style='min-width:180px'>Cost Center <span class='pis2-warn-badge'>? Updates GL</span></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo(this.$items_card);
        var $tbody = $itbl.find("tbody");

        $.each(data.items, function (_, row) {
            var $tr = $("<tr></tr>").attr("data-row-name", row.name).appendTo($tbody);
            $tr.append("<td>" + row.idx + "</td>");
            $tr.append("<td>" + (row.item_code || "") + "</td>");
            $tr.append("<td>" + (row.item_name || "") + "</td>");
            $tr.append("<td>" + row.qty + "</td>");
            $tr.append("<td>" + format_currency(row.rate) + "</td>");

            // Item Group
            var $td_ig = $("<td></td>").appendTo($tr);
            var ig_ctrl = frappe.ui.form.make_control({
                df: { fieldtype: "Link", fieldname: "ig_" + row.name,
                      options: "Item Group", label: "", placeholder: "Item Group" },
                parent: $("<div></div>").appendTo($td_ig), render_input: true,
            });
            ig_ctrl.set_value(row.item_group || ""); ig_ctrl.refresh();
            $tr.data("ig_ctrl", ig_ctrl);

            // Expense Account
            var $td_ea = $("<td></td>").appendTo($tr);
            var ea_ctrl = frappe.ui.form.make_control({
                df: {
                    fieldtype: "Link", fieldname: "ea_" + row.name,
                    options: "Account", label: "", placeholder: "Expense Account",
                    filters: { account_type: ["in", ["Expense Account", "Cost of Goods Sold", "Expenses Included In Valuation", "Stock Adjustment"]] },
                },
                parent: $("<div></div>").appendTo($td_ea), render_input: true,
            });
            ea_ctrl.set_value(row.expense_account || ""); ea_ctrl.refresh();
            $tr.data("ea_ctrl", ea_ctrl);

            // Cost Center
            var $td_cc = $("<td></td>").appendTo($tr);
            var cc_ctrl = frappe.ui.form.make_control({
                df: { fieldtype: "Link", fieldname: "cc_" + row.name,
                      options: "Cost Center", label: "", placeholder: "Cost Center" },
                parent: $("<div></div>").appendTo($td_cc), render_input: true,
            });
            cc_ctrl.set_value(row.cost_center || ""); cc_ctrl.refresh();
            $tr.data("cc_ctrl", cc_ctrl);
        });

        this.$save_row.show();
        this.$result.empty();
    },

    _meta: function (label, value) {
        return '<div class="pis2-meta-item">' +
               '<span class="pis2-meta-label">' + label + "</span>" +
               '<span class="pis2-meta-value">' + (value || "-") + "</span></div>";
    },

    save_changes: function () {
        var me = this;
        if (!me.pi_data) return;

        var items = [];
        me.$items_card.find("tbody tr").each(function () {
            var $tr = $(this);
            items.push({
                name:            $tr.attr("data-row-name"),
                item_group:      $tr.data("ig_ctrl") ? $tr.data("ig_ctrl").get_value() : "",
                expense_account: $tr.data("ea_ctrl") ? $tr.data("ea_ctrl").get_value() : "",
                cost_center:     $tr.data("cc_ctrl") ? $tr.data("cc_ctrl").get_value() : "",
            });
        });

        var new_posting_date = me.posting_date_ctrl ? me.posting_date_ctrl.get_value() : "";

        // Warn before changing posting date
        if (new_posting_date && new_posting_date !== me.pi_data.posting_date) {
            frappe.confirm(
                __("Changing the posting date to <b>{0}</b> will update all linked GL entries and Payment Ledger entries. Are you sure?", [new_posting_date]),
                function () { me._do_save(items, new_posting_date); }
            );
        } else {
            me._do_save(items, "");
        }
    },

    _do_save: function (items, new_posting_date) {
        var me = this;

        var args = {
            pi_name: me.pi_data.pi_name,
            items: JSON.stringify(items),
        };
        if (new_posting_date) {
            args.new_posting_date = new_posting_date;
        }

        frappe.call({
            method: PIS2_METHOD_BASE + "patch_pi_fields",
            args: args,
            freeze: true, freeze_message: __("Saving changes..."),
            callback: function (r) {
                if (!r.message) return;
                me.$result.empty();
                if (r.message.status === "no_changes") {
                    frappe.show_alert({ message: __("No changes to save."), indicator: "blue" });
                    return;
                }
                frappe.show_alert({ message: __("Purchase Invoice updated successfully."), indicator: "green" });
                var html = '<div class="pis2-changes"><b>Changes saved:</b><ul>';
                $.each(r.message.changes || [], function (_, c) {
                    html += "<li>" + frappe.utils.escape_html(c) + "</li>";
                });
                html += "</ul></div>";
                me.$result.html(html);
                me.load_pi();   // Reload to reflect new values
            },
        });
    },
});