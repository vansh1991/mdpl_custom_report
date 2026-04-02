frappe.pages["patch-invoice-fields"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Patch Invoice Fields",
        single_column: true,
    });
    new PatchInvoicePage(page, wrapper);
};

var PIF_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_invoice_fields.patch_invoice_fields.";

var PatchInvoicePage = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.invoice_data = null;
        this.all_sales_persons = [];
        this.payment_terms_list = [];
        this.due_date_ctrl = null;
        this.payment_terms_ctrl = null;
        this.make();
        this._load_sales_persons();
    },

    _load_sales_persons: function () {
        var me = this;
        frappe.call({
            method: PIF_METHOD_BASE + "get_all_sales_persons",
            callback: function (r) {
                if (r.message) {
                    me.all_sales_persons = r.message;
                }
            },
        });
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".pif-wrap { max-width: 960px; margin: 24px auto; padding: 0 16px; }" +
            ".pif-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 24px; }" +
            ".pif-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".pif-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".pif-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 14px; }" +
            ".pif-meta { display: flex; gap: 32px; flex-wrap: wrap; margin-bottom: 14px; }" +
            ".pif-meta-item { display: flex; flex-direction: column; gap: 2px; }" +
            ".pif-meta-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; }" +
            ".pif-meta-value { font-size: 14px; font-weight: 500; color: var(--text-color); }" +
            ".pif-patch-row { display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-end; padding-top: 14px; border-top: 1px solid var(--border-color); margin-top: 4px; }" +
            ".pif-patch-field { display: flex; flex-direction: column; gap: 4px; min-width: 200px; flex: 1; }" +
            ".pif-patch-field label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; }" +
            ".pif-patch-field select { height: 32px; font-size: 13px; padding: 0 8px; border: 1px solid var(--border-color); border-radius: var(--border-radius); background: var(--control-bg); color: var(--text-color); width: 100%; }" +
            ".pif-warn-badge { display: inline-block; background: var(--yellow-100,#fef3cd); color: var(--yellow-700,#854d0e); border-radius: 4px; font-size: 10px; padding: 1px 6px; margin-left: 6px; font-weight: 600; vertical-align: middle; }" +
            ".pif-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".pif-table th { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px; border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".pif-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color); vertical-align: middle; font-size: 13px; }" +
            ".pif-table tr:last-child td { border-bottom: none; }" +
            ".pif-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".pif-table .link-btn { display: none !important; }" +
            ".pif-sp-select { height: 30px; font-size: 12px; padding: 2px 6px; border: 1px solid var(--border-color); border-radius: var(--border-radius); background: var(--control-bg); color: var(--text-color); width: 100%; }" +
            ".pif-add-row { margin-top: 10px; }" +
            ".pif-remove-btn { color: var(--red); cursor: pointer; font-size: 14px; padding: 2px 6px; background: none; border: none; }" +
            ".pif-remove-btn:hover { opacity: .7; }" +
            ".pif-changes { margin-top: 12px; padding: 12px 16px; background: var(--alert-bg-success); border: 1px solid var(--alert-border-success); border-radius: var(--border-radius); font-size: 12px; color: var(--alert-text-success); }" +
            ".pif-changes ul { margin: 6px 0 0 16px; }" +
            ".pif-pct-warning { font-size: 11px; color: var(--text-muted); margin-top: 6px; }"
        );

        this.$wrap = $('<div class="pif-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        // Search row
        var $search = $('<div class="pif-search-row"></div>').appendTo(this.$wrap);
        this.invoice_field = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "sales_invoice",
                options: "Sales Invoice", label: "Sales Invoice",
                filters: { docstatus: 1 },
                placeholder: "Search submitted invoice...",
            },
            parent: $search, render_input: true,
        });
        this.invoice_field.refresh();

        $('<button class="btn btn-primary btn-sm" style="height:32px;white-space:nowrap">Load Invoice</button>')
            .appendTo($search)
            .on("click", function () { me.load_invoice(); });

        this.$info       = $('<div class="pif-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$items_card = $('<div class="pif-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$st_card    = $('<div class="pif-card" style="display:none"></div>').appendTo(this.$wrap);
        this.$save_row   = $('<div style="display:none;margin-bottom:32px;"></div>').appendTo(this.$wrap);

        $('<button class="btn btn-primary">Save Changes</button>')
            .appendTo(this.$save_row)
            .on("click", function () { me.save_changes(); });

        this.$result = $('<div></div>').appendTo(this.$wrap);

        $(this.invoice_field.input).on("keydown", function (e) {
            if (e.which === 13) me.load_invoice();
        });
    },

    load_invoice: function () {
        var me = this;
        var inv = (this.invoice_field.get_value() || "").trim();
        if (!inv) { frappe.msgprint(__("Please enter a Sales Invoice name.")); return; }

        frappe.call({
            method: PIF_METHOD_BASE + "get_invoice_details",
            args: { invoice_name: inv },
            freeze: true, freeze_message: __("Loading invoice..."),
            callback: function (r) {
                if (r.message) {
                    me.invoice_data = r.message;
                    if (r.message.all_sales_persons && r.message.all_sales_persons.length) {
                        me.all_sales_persons = r.message.all_sales_persons;
                    }
                    if (r.message.payment_terms_list) {
                        me.payment_terms_list = r.message.payment_terms_list;
                    }
                    me.render(r.message);
                }
            },
        });
    },

    render: function (data) {
        var me = this;

        // -- Info card with due date + payment terms patch fields --
        this.$info.empty().show().append('<div class="pif-card-title">Invoice Details</div>');

        // Static meta row
        var $meta = $('<div class="pif-meta"></div>').appendTo(this.$info);
        $meta.html(
            me._meta("Invoice",     data.invoice_name) +
            me._meta("Customer",    data.customer) +
            me._meta("Date",        data.posting_date) +
            me._meta("Grand Total", format_currency(data.grand_total)) +
            me._meta("Status",      data.status) +
            me._meta("Current Due Date", data.due_date || "-") +
            me._meta("Payment Terms", data.payment_terms_template || "-")
        );

        // Patch fields row
        var $patch = $('<div class="pif-patch-row"></div>').appendTo(this.$info);

        // Due Date
        var $due_wrap = $('<div class="pif-patch-field"></div>').appendTo($patch);
        $due_wrap.append('<label>Change Due Date <span class="pif-warn-badge">Updates PLE</span></label>');
        var $due_ctrl_wrap = $('<div></div>').appendTo($due_wrap);
        this.due_date_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "new_due_date", label: "",
                  placeholder: "Leave blank to keep current" },
            parent: $due_ctrl_wrap, render_input: true,
        });
        this.due_date_ctrl.set_value(data.due_date || "");
        this.due_date_ctrl.refresh();

        // Payment Terms Template
        var $pt_wrap = $('<div class="pif-patch-field"></div>').appendTo($patch);
        $pt_wrap.append('<label>Change Payment Terms Template</label>');
        var $pt_sel = $('<select class="pif-sp-select" style="height:32px"></select>');
        $pt_sel.append('<option value="">(No change / clear)</option>');
        $.each(me.payment_terms_list, function (_, pt) {
            var $opt = $('<option></option>').val(pt.name).text(pt.name);
            if (pt.name === data.payment_terms_template) {
                $opt.prop("selected", true);
            }
            $pt_sel.append($opt);
        });
        $pt_wrap.append($pt_sel);
        this.$pt_select = $pt_sel;

        // -- Items card --
        this.$items_card.empty().show().append('<div class="pif-card-title">Item Groups</div>');
        var $itbl = $(
            '<table class="pif-table"><thead><tr>' +
            "<th>#</th><th>Item Code</th><th>Item Name</th>" +
            "<th>Qty</th><th>Rate</th><th style='min-width:200px'>Item Group</th>" +
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

            var $td_group = $("<td></td>").appendTo($tr);
            var ctrl = frappe.ui.form.make_control({
                df: { fieldtype: "Link", fieldname: "item_group_" + row.name,
                      options: "Item Group", label: "", placeholder: "Select Item Group" },
                parent: $("<div></div>").appendTo($td_group), render_input: true,
            });
            ctrl.set_value(row.item_group || "");
            ctrl.refresh();
            $tr.data("item_group_ctrl", ctrl);
        });

        // -- Sales Team card --
        this.$st_card.empty().show().append('<div class="pif-card-title">Sales Team</div>');
        var $stable = $(
            '<table class="pif-table" id="pif-st-table"><thead><tr>' +
            "<th>#</th><th style='min-width:220px'>Sales Person</th>" +
            "<th>Allocated %</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo(this.$st_card);
        this.$st_card.append('<div class="pif-pct-warning">Total allocated % should equal 100.</div>');

        var $stbody = $stable.find("tbody");
        $.each(data.sales_team, function (_, row) { me._add_st_row($stbody, row); });

        $('<button class="btn btn-xs btn-default pif-add-row">+ Add Row</button>')
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
        var $sel = $('<select class="pif-sp-select"></select>');
        $sel.append('<option value="">-- Select Sales Person --</option>');
        $.each(me.all_sales_persons, function (_, sp) {
            var label = sp.name;
            if (sp.sales_person_name && sp.sales_person_name !== sp.name) {
                label += " (" + sp.sales_person_name + ")";
            }
            var $opt = $("<option></option>").val(sp.name).text(label);
            if (sp.name === (row.sales_person || "")) { $opt.prop("selected", true); }
            $sel.append($opt);
        });
        $td_sp.append($sel);
        $tr.data("sp_sel", $sel);

        var $td_pct = $("<td></td>").appendTo($tr);
        var $pct = $('<input type="number" class="form-control" min="0" max="100" step="0.01"/>')
            .val(row.allocated_percentage || 0).appendTo($td_pct);
        $tr.data("pct_input", $pct);

        $("<td></td>").appendTo($tr).append(
            $('<button class="pif-remove-btn" title="Remove">x</button>')
                .on("click", function () { $tr.remove(); })
        );
    },

    _meta: function (label, value) {
        return '<div class="pif-meta-item">' +
               '<span class="pif-meta-label">' + label + '</span>' +
               '<span class="pif-meta-value">' + (value || "-") + '</span></div>';
    },

    save_changes: function () {
        var me = this;
        if (!me.invoice_data) return;

        var items = [];
        me.$items_card.find("tbody tr").each(function () {
            var $tr = $(this);
            var ctrl = $tr.data("item_group_ctrl");
            items.push({ name: $tr.attr("data-row-name"), item_group: ctrl ? ctrl.get_value() : "" });
        });

        var sales_team = [];
        var total_pct = 0;
        me.$st_card.find("#pif-st-table tbody tr").each(function () {
            var $tr  = $(this);
            var $sel = $tr.data("sp_sel");
            var pct  = parseFloat($tr.data("pct_input").val()) || 0;
            total_pct += pct;
            sales_team.push({
                name:                 $tr.attr("data-row-name") || "",
                sales_person:         $sel ? $sel.val() : "",
                allocated_percentage: pct,
            });
        });

        var new_due_date       = me.due_date_ctrl ? me.due_date_ctrl.get_value() : "";
        var new_payment_terms  = me.$pt_select ? me.$pt_select.val() : "";

        if (sales_team.length > 0 && Math.abs(total_pct - 100) > 0.1) {
            frappe.confirm(
                __("Total allocated percentage is {0}%, not 100%. Save anyway?", [total_pct.toFixed(2)]),
                function () { me._do_save(items, sales_team, new_due_date, new_payment_terms); }
            );
            return;
        }

        me._do_save(items, sales_team, new_due_date, new_payment_terms);
    },

    _do_save: function (items, sales_team, new_due_date, new_payment_terms) {
        var me = this;
        frappe.call({
            method: PIF_METHOD_BASE + "patch_invoice_fields",
            args: {
                invoice_name:       me.invoice_data.invoice_name,
                items:              JSON.stringify(items),
                sales_team:         JSON.stringify(sales_team),
                new_due_date:       new_due_date || "",
                new_payment_terms:  new_payment_terms || "",
            },
            freeze: true, freeze_message: __("Saving changes..."),
            callback: function (r) {
                if (!r.message) return;
                me.$result.empty();
                if (r.message.status === "no_changes") {
                    frappe.show_alert({ message: __("No changes to save."), indicator: "blue" });
                    return;
                }
                frappe.show_alert({ message: __("Invoice updated successfully."), indicator: "green" });
                var html = '<div class="pif-changes"><b>Changes saved:</b><ul>';
                $.each(r.message.changes || [], function (_, c) {
                    html += "<li>" + frappe.utils.escape_html(c) + "</li>";
                });
                html += "</ul></div>";
                me.$result.html(html);
                me.load_invoice();
            },
        });
    },
});