frappe.pages["patch-dn-single"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Patch Delivery Note Fields",
        single_column: true,
    });
    new PatchDNSingle(page, wrapper);
};

var PDS_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_dn_single.patch_dn_single.";

var PatchDNSingle = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.dn_data = null;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".pds-wrap { max-width: 1020px; margin: 24px auto; padding: 0 16px; }" +
            ".pds-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 20px; }" +
            ".pds-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".pds-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".pds-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 14px; }" +
            ".pds-meta { display: flex; gap: 32px; flex-wrap: wrap; margin-bottom: 8px; }" +
            ".pds-meta-item { display: flex; flex-direction: column; gap: 2px; }" +
            ".pds-meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; }" +
            ".pds-meta-value { font-size: 14px; font-weight: 500; color: var(--text-color); }" +
            ".pds-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".pds-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".pds-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".pds-table tr:last-child td { border-bottom: none; }" +
            ".pds-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".pds-table .link-btn { display: none !important; }" +
            ".pds-remove-btn { color: var(--red); cursor: pointer; font-size: 14px;" +
            "  padding: 2px 6px; background: none; border: none; }" +
            ".pds-remove-btn:hover { opacity:.7; }" +
            ".pds-pct-warning { font-size: 11px; color: var(--text-muted); margin-top: 6px; }" +
            ".pds-changes { margin-top: 12px; padding: 12px 16px;" +
            "  background: var(--alert-bg-success); border: 1px solid var(--alert-border-success);" +
            "  border-radius: var(--border-radius); font-size: 12px; color: var(--alert-text-success); }" +
            ".pds-changes ul { margin: 6px 0 0 16px; }"
        );

        this.$wrap = $('<div class="pds-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        var $search = $('<div class="pds-search-row"></div>').appendTo(this.$wrap);
        this.dn_field = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "delivery_note",
                options: "Delivery Note", label: "Delivery Note",
                filters: { docstatus: 1 },
                placeholder: "Search submitted delivery note...",
            },
            parent: $search, render_input: true,
        });
        this.dn_field.refresh();

        $('<button class="btn btn-primary btn-sm" style="height:32px;white-space:nowrap">Load DN</button>')
            .appendTo($search).on("click", function () { me.load_dn(); });

        $(this.dn_field.input).on("keydown", function (e) {
            if (e.which === 13) me.load_dn();
        });

        this.$info       = $('<div class="pds-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$items_card = $('<div class="pds-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$st_card    = $('<div class="pds-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$save_row   = $('<div style="display:none;margin-bottom:32px;"></div>').appendTo(this.$wrap);

        $('<button class="btn btn-primary">Save Changes</button>')
            .appendTo(this.$save_row).on("click", function () { me.save_changes(); });

        this.$result = $('<div></div>').appendTo(this.$wrap);
    },

    load_dn: function () {
        var me = this;
        var dn = (this.dn_field.get_value() || "").trim();
        if (!dn) { frappe.msgprint(__("Please enter a Delivery Note name.")); return; }

        frappe.call({
            method: PDS_METHOD_BASE + "get_dn_details",
            args: { dn_name: dn },
            freeze: true, freeze_message: __("Loading delivery note..."),
            callback: function (r) {
                if (r.message) { me.dn_data = r.message; me.render(r.message); }
            },
        });
    },

    render: function (data) {
        var me = this;

        this.$info.empty().show().append(
            '<div class="pds-card-title">Delivery Note Details</div>' +
            '<div class="pds-meta">' +
            me._meta("Delivery Note", data.dn_name) +
            me._meta("Customer", data.customer) +
            me._meta("Date", data.posting_date) +
            me._meta("Grand Total", format_currency(data.grand_total)) +
            me._meta("Status", data.status) +
            "</div>"
        );

        // Items
        this.$items_card.empty().show().append('<div class="pds-card-title">Item Groups</div>');
        var $itbl = $(
            '<table class="pds-table"><thead><tr>' +
            "<th>#</th><th>Item Code</th><th>Item Name</th><th>Qty</th><th>Rate</th>" +
            "<th>Warehouse</th><th style='min-width:200px'>Item Group</th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo(this.$items_card);
        var $itbody = $itbl.find("tbody");

        $.each(data.items, function (_, row) {
            var $tr = $("<tr></tr>").attr("data-row-name", row.name).appendTo($itbody);
            $tr.append("<td>" + row.idx + "</td>");
            $tr.append("<td>" + (row.item_code || "") + "</td>");
            $tr.append("<td>" + (row.item_name || "") + "</td>");
            $tr.append("<td>" + row.qty + "</td>");
            $tr.append("<td>" + format_currency(row.rate) + "</td>");
            $tr.append("<td>" + (row.warehouse || "") + "</td>");
            var $td = $("<td></td>").appendTo($tr);
            var ctrl = frappe.ui.form.make_control({
                df: { fieldtype: "Link", fieldname: "ig_" + row.name,
                      options: "Item Group", label: "", placeholder: "Select Item Group" },
                parent: $("<div></div>").appendTo($td), render_input: true,
            });
            ctrl.set_value(row.item_group || ""); ctrl.refresh();
            $tr.data("item_group_ctrl", ctrl);
        });

        // Sales Team
        this.$st_card.empty().show().append('<div class="pds-card-title">Sales Team</div>');
        var $stable = $(
            '<table class="pds-table" id="pds-st-table"><thead><tr>' +
            "<th>#</th><th style='min-width:220px'>Sales Person</th><th>Allocated %</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo(this.$st_card);
        this.$st_card.append('<div class="pds-pct-warning">Total allocated % should equal 100.</div>');
        var $stbody = $stable.find("tbody");

        $.each(data.sales_team, function (_, row) { me._add_st_row($stbody, row); });

        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo(this.$st_card)
            .on("click", function () {
                me._add_st_row($stbody, {
                    name: "", idx: $stbody.find("tr").length + 1,
                    sales_person: "", allocated_percentage: 0,
                });
            });

        this.$save_row.show();
        this.$result.empty();
    },

    _add_st_row: function ($stbody, row) {
        var me = this;
        var $tr = $("<tr></tr>").attr("data-row-name", row.name || "").appendTo($stbody);
        $tr.append("<td>" + (row.idx || $stbody.find("tr").length) + "</td>");

        var $td_sp = $("<td></td>").appendTo($tr);
        var sp_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "sp_" + (row.name || frappe.utils.get_random(6)),
                  options: "Sales Person", label: "", placeholder: "Sales Person" },
            parent: $("<div></div>").appendTo($td_sp), render_input: true,
        });
        sp_ctrl.set_value(row.sales_person || ""); sp_ctrl.refresh();
        $tr.data("sp_ctrl", sp_ctrl);

        var $td_pct = $("<td></td>").appendTo($tr);
        var $pct = $('<input type="number" class="form-control" min="0" max="100" step="0.01"/>')
            .val(row.allocated_percentage || 0).appendTo($td_pct);
        $tr.data("pct_input", $pct);

        $("<td></td>").appendTo($tr).append(
            $('<button class="pds-remove-btn" title="Remove">x</button>')
                .on("click", function () { $tr.remove(); })
        );
    },

    _meta: function (label, value) {
        return '<div class="pds-meta-item">' +
               '<span class="pds-meta-label">' + label + "</span>" +
               '<span class="pds-meta-value">' + (value || "-") + "</span></div>";
    },

    save_changes: function () {
        var me = this;
        if (!me.dn_data) return;

        var items = [];
        me.$items_card.find("tbody tr").each(function () {
            var $tr = $(this);
            var ctrl = $tr.data("item_group_ctrl");
            items.push({ name: $tr.attr("data-row-name"), item_group: ctrl ? ctrl.get_value() : "" });
        });

        var sales_team = [], total_pct = 0;
        me.$st_card.find("#pds-st-table tbody tr").each(function () {
            var $tr = $(this);
            var sp_ctrl = $tr.data("sp_ctrl");
            var pct = parseFloat($tr.data("pct_input").val()) || 0;
            total_pct += pct;
            sales_team.push({
                name: $tr.attr("data-row-name") || "",
                sales_person: sp_ctrl ? sp_ctrl.get_value() : "",
                allocated_percentage: pct,
            });
        });

        if (sales_team.length > 0 && Math.abs(total_pct - 100) > 0.1) {
            frappe.confirm(
                __("Total allocated % is {0}%, not 100%. Save anyway?", [total_pct.toFixed(2)]),
                function () { me._do_save(items, sales_team); }
            );
            return;
        }
        me._do_save(items, sales_team);
    },

    _do_save: function (items, sales_team) {
        var me = this;
        frappe.call({
            method: PDS_METHOD_BASE + "patch_dn_fields",
            args: {
                dn_name: me.dn_data.dn_name,
                items: JSON.stringify(items),
                sales_team: JSON.stringify(sales_team),
            },
            freeze: true, freeze_message: __("Saving changes..."),
            callback: function (r) {
                if (!r.message) return;
                me.$result.empty();
                if (r.message.status === "no_changes") {
                    frappe.show_alert({ message: __("No changes to save."), indicator: "blue" });
                    return;
                }
                frappe.show_alert({ message: __("Delivery Note updated successfully."), indicator: "green" });
                var html = '<div class="pds-changes"><b>Changes saved:</b><ul>';
                $.each(r.message.changes || [], function (_, c) {
                    html += "<li>" + frappe.utils.escape_html(c) + "</li>";
                });
                html += "</ul></div>";
                me.$result.html(html);
                me.load_dn();
            },
        });
    },
});