frappe.pages["patch-pr-single"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Patch Purchase Receipt Fields",
        single_column: true,
    });
    new PatchPRSingle(page, wrapper);
};

var PRS_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_pr_single.patch_pr_single.";

var PatchPRSingle = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.pr_data = null;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".prs-wrap { max-width: 1020px; margin: 24px auto; padding: 0 16px; }" +
            ".prs-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 20px; }" +
            ".prs-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".prs-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".prs-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 14px; }" +
            ".prs-meta { display: flex; gap: 32px; flex-wrap: wrap; margin-bottom: 8px; }" +
            ".prs-meta-item { display: flex; flex-direction: column; gap: 2px; }" +
            ".prs-meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; }" +
            ".prs-meta-value { font-size: 14px; font-weight: 500; color: var(--text-color); }" +
            ".prs-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".prs-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".prs-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".prs-table tr:last-child td { border-bottom: none; }" +
            ".prs-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".prs-table .link-btn { display: none !important; }" +
            ".prs-changes { margin-top: 12px; padding: 12px 16px;" +
            "  background: var(--alert-bg-success); border: 1px solid var(--alert-border-success);" +
            "  border-radius: var(--border-radius); font-size: 12px; color: var(--alert-text-success); }" +
            ".prs-changes ul { margin: 6px 0 0 16px; }"
        );

        this.$wrap = $('<div class="prs-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        var $search = $('<div class="prs-search-row"></div>').appendTo(this.$wrap);
        this.pr_field = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "purchase_receipt",
                options: "Purchase Receipt", label: "Purchase Receipt",
                filters: { docstatus: 1 },
                placeholder: "Search submitted purchase receipt...",
            },
            parent: $search, render_input: true,
        });
        this.pr_field.refresh();

        $('<button class="btn btn-primary btn-sm" style="height:32px;white-space:nowrap">Load PR</button>')
            .appendTo($search).on("click", function () { me.load_pr(); });
        $(this.pr_field.input).on("keydown", function (e) { if (e.which === 13) me.load_pr(); });

        this.$info       = $('<div class="prs-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$items_card = $('<div class="prs-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$save_row   = $('<div style="display:none;margin-bottom:32px;"></div>').appendTo(this.$wrap);
        $('<button class="btn btn-primary">Save Changes</button>')
            .appendTo(this.$save_row).on("click", function () { me.save_changes(); });
        this.$result = $('<div></div>').appendTo(this.$wrap);
    },

    load_pr: function () {
        var me = this;
        var pr = (this.pr_field.get_value() || "").trim();
        if (!pr) { frappe.msgprint(__("Please enter a Purchase Receipt name.")); return; }

        frappe.call({
            method: PRS_METHOD_BASE + "get_pr_details",
            args: { pr_name: pr },
            freeze: true, freeze_message: __("Loading purchase receipt..."),
            callback: function (r) {
                if (r.message) { me.pr_data = r.message; me.render(r.message); }
            },
        });
    },

    render: function (data) {
        var me = this;

        this.$info.empty().show().append(
            '<div class="prs-card-title">Purchase Receipt Details</div>' +
            '<div class="prs-meta">' +
            me._meta("Purchase Receipt", data.pr_name) +
            me._meta("Supplier", data.supplier) +
            me._meta("Date", data.posting_date) +
            me._meta("Grand Total", format_currency(data.grand_total)) +
            me._meta("Status", data.status) +
            "</div>"
        );

        this.$items_card.empty().show().append('<div class="prs-card-title">Items</div>');
        var $itbl = $(
            '<table class="prs-table"><thead><tr>' +
            "<th>#</th><th>Item Code</th><th>Item Name</th><th>Qty</th><th>Rate</th>" +
            "<th>Warehouse</th>" +
            "<th style='min-width:180px'>Item Group</th>" +
            "<th style='min-width:180px'>Cost Center</th>" +
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
            $tr.append("<td>" + (row.warehouse || "") + "</td>");

            // Item Group
            var $td_ig = $("<td></td>").appendTo($tr);
            var ig_ctrl = frappe.ui.form.make_control({
                df: { fieldtype: "Link", fieldname: "ig_" + row.name,
                      options: "Item Group", label: "", placeholder: "Item Group" },
                parent: $("<div></div>").appendTo($td_ig), render_input: true,
            });
            ig_ctrl.set_value(row.item_group || ""); ig_ctrl.refresh();
            $tr.data("ig_ctrl", ig_ctrl);

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
        return '<div class="prs-meta-item">' +
               '<span class="prs-meta-label">' + label + "</span>" +
               '<span class="prs-meta-value">' + (value || "-") + "</span></div>";
    },

    save_changes: function () {
        var me = this;
        if (!me.pr_data) return;

        var items = [];
        me.$items_card.find("tbody tr").each(function () {
            var $tr = $(this);
            items.push({
                name: $tr.attr("data-row-name"),
                item_group: $tr.data("ig_ctrl") ? $tr.data("ig_ctrl").get_value() : "",
                cost_center: $tr.data("cc_ctrl") ? $tr.data("cc_ctrl").get_value() : "",
            });
        });

        frappe.call({
            method: PRS_METHOD_BASE + "patch_pr_fields",
            args: { pr_name: me.pr_data.pr_name, items: JSON.stringify(items) },
            freeze: true, freeze_message: __("Saving changes..."),
            callback: function (r) {
                if (!r.message) return;
                me.$result.empty();
                if (r.message.status === "no_changes") {
                    frappe.show_alert({ message: __("No changes to save."), indicator: "blue" }); return;
                }
                frappe.show_alert({ message: __("Purchase Receipt updated successfully."), indicator: "green" });
                var html = '<div class="prs-changes"><b>Changes saved:</b><ul>';
                $.each(r.message.changes || [], function (_, c) {
                    html += "<li>" + frappe.utils.escape_html(c) + "</li>";
                });
                html += "</ul></div>";
                me.$result.html(html);
                me.load_pr();
            },
        });
    },
});