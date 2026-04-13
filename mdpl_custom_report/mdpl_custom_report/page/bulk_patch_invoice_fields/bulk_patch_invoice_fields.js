frappe.pages["bulk-patch-invoice-fields"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Bulk Patch Invoice Fields",
        single_column: true,
    });
    new BulkPatchPage(page, wrapper);
};

var BULK_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.bulk_patch_invoice_fields.bulk_patch_invoice_fields.";

var BulkPatchPage = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.all_sales_persons = [];
        this.make();
        this._load_sales_persons();
    },

    // Load ALL sales persons from backend (ignore_permissions=True)
    _load_sales_persons: function () {
        var me = this;
        frappe.call({
            method: BULK_METHOD_BASE + "get_all_sales_persons",
            callback: function (r) {
                if (r.message) {
                    me.all_sales_persons = r.message;
                    // Refresh any existing rows
                    me._refresh_sp_selects();
                }
            },
        });
    },

    // Repopulate any already-rendered sales person selects
    _refresh_sp_selects: function () {
        var me = this;
        if (!me.$st_tbody) return;
        me.$st_tbody.find("tr").each(function () {
            var $tr = $(this);
            var $sel = $tr.data("sp_sel");
            if (!$sel) return;
            var current = $sel.val();
            $sel.empty().append($('<option value="">-- Select Sales Person --</option>'));
            $.each(me.all_sales_persons, function (_, sp) {
                var label = sp.name + (sp.sales_person_name && sp.sales_person_name !== sp.name
                    ? " (" + sp.sales_person_name + ")" : "");
                var $opt = $("<option></option>").val(sp.name).text(label);
                if (sp.name === current) $opt.prop("selected", true);
                $sel.append($opt);
            });
        });
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".bp-wrap { max-width: 1020px; margin: 24px auto; padding: 0 16px; }" +
            ".bp-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".bp-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }" +
            ".bp-card-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; }" +
            ".bp-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 12px; }" +
            ".bp-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".bp-filter-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 14px; flex-wrap: wrap; }" +
            ".bp-filter-row .frappe-control { flex: 1; min-width: 160px; margin: 0; }" +
            ".bp-inv-pool { min-height: 44px; padding: 6px 8px; border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius); display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }" +
            ".bp-tag { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px;" +
            "  background: var(--bg-blue); color: var(--text-on-blue); border-radius: 12px; font-size: 12px; }" +
            ".bp-tag .rm { cursor: pointer; font-size: 13px; opacity: .6; margin-left: 2px; }" +
            ".bp-tag .rm:hover { opacity: 1; }" +
            ".bp-pool-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 4px; }" +
            ".bp-count { font-size: 12px; color: var(--text-muted); }" +
            ".bp-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".bp-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".bp-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".bp-table tr:last-child td { border-bottom: none; }" +
            ".bp-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".bp-table .link-btn { display: none !important; }" +
            ".bp-sp-select { height: 30px; font-size: 12px; padding: 2px 6px;" +
            "  border: 1px solid var(--border-color); border-radius: var(--border-radius);" +
            "  background: var(--control-bg); color: var(--text-color); width: 100%; }" +
            ".bp-rm-btn { color: var(--red); cursor: pointer; font-size: 14px;" +
            "  padding: 2px 6px; background: none; border: none; }" +
            ".bp-rm-btn:hover { opacity: .7; }" +
            ".bp-pct-note { font-size: 11px; color: var(--text-muted); margin-top: 6px; }" +
            ".bp-progress-track { height: 6px; border-radius: 3px; background: var(--border-color); margin: 8px 0; }" +
            ".bp-progress-bar { height: 6px; border-radius: 3px; background: var(--primary); transition: width .4s; }" +
            ".bp-prog-label { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }" +
            ".bp-result-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 12px; }" +
            ".bp-result-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; padding: 5px 8px; border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".bp-result-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-color); vertical-align: top; }" +
            ".bp-result-table tr:last-child td { border-bottom: none; }" +
            ".tag-ok { color: var(--green); font-weight: 600; }" +
            ".tag-skip { color: var(--text-muted); }" +
            ".tag-err { color: var(--red); font-weight: 600; }" +
            ".bp-summary { display: flex; gap: 16px; padding: 12px 16px; border-radius: var(--border-radius);" +
            "  background: var(--control-bg); margin-bottom: 14px; flex-wrap: wrap; }" +
            ".bp-summary-item { display: flex; flex-direction: column; gap: 2px; }" +
            ".bp-summary-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; }" +
            ".bp-summary-val { font-size: 18px; font-weight: 600; }"
        );

        this.$wrap = $('<div class="bp-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        this._build_step1();
        this._build_step2();
        this._build_step3();
        this._build_apply();
        this._build_results();
    },

    // STEP 1 - SELECT INVOICES
    _build_step1: function () {
        var me = this;
        var $c = $('<div class="bp-card"></div>').appendTo(this.$wrap);
        $c.append('<div class="bp-card-title">Step 1 - Select Invoices</div>');
        $c.append(
            '<div class="bp-card-desc">Add invoices manually one by one, or use the filters ' +
            'below to fetch all submitted invoices matching a customer and date range at once.</div>'
        );

        var $sr = $('<div class="bp-search-row"></div>').appendTo($c);
        this.inv_field = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "bp_inv",
                options: "Sales Invoice", label: "Add Invoice",
                filters: { docstatus: 1 },
                placeholder: "Type invoice name and press Add...",
            },
            parent: $sr, render_input: true,
        });
        this.inv_field.refresh();
        $('<button class="btn btn-default btn-sm" style="height:32px;white-space:nowrap">Add</button>')
            .appendTo($sr)
            .on("click", function () { me._add_invoice(); });
        $(this.inv_field.input).on("keydown", function (e) {
            if (e.which === 13) me._add_invoice();
        });

        var $fr = $('<div class="bp-filter-row"></div>').appendTo($c);
        this.f_customer = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "bp_cust", options: "Customer",
                  label: "Customer", placeholder: "All customers" },
            parent: $fr, render_input: true,
        });
        this.f_customer.refresh();
        this.f_from = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "bp_from", label: "From Date" },
            parent: $fr, render_input: true,
        });
        this.f_from.refresh();
        this.f_to = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "bp_to", label: "To Date" },
            parent: $fr, render_input: true,
        });
        this.f_to.refresh();
        this.f_company = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "bp_company", options: "Company",
                  label: "Company",
                  default: frappe.defaults.get_user_default("Company") },
            parent: $fr, render_input: true,
        });
        this.f_company.refresh();
        this.f_company.set_value(frappe.defaults.get_user_default("Company") || "");

        $('<button class="btn btn-primary btn-sm" style="height:32px;white-space:nowrap">Fetch Invoices</button>')
            .appendTo($fr)
            .on("click", function () { me._fetch_by_filter(); });

        this.$pool = $('<div class="bp-inv-pool"></div>').appendTo($c);
        var $footer = $('<div class="bp-pool-footer"></div>').appendTo($c);
        this.$count_label = $('<span class="bp-count">0 invoices selected</span>').appendTo($footer);
        $('<button class="btn btn-xs btn-default">Clear All</button>')
            .appendTo($footer)
            .on("click", function () { me.$pool.empty(); me._update_count(); });
    },

    _add_invoice: function () {
        var me = this;
        var inv = (this.inv_field.get_value() || "").trim();
        if (!inv) return;
        if (me.$pool.find('[data-inv="' + inv + '"]').length) {
            frappe.show_alert({ message: inv + " already added.", indicator: "orange" });
            return;
        }
        me._append_tag(inv);
        me.inv_field.set_value("");
        me._update_count();
    },

    _append_tag: function (inv) {
        var me = this;
        var $tag = $('<span class="bp-tag"></span>').attr("data-inv", inv).text(inv);
        $('<span class="rm">x</span>').appendTo($tag)
            .on("click", function () { $tag.remove(); me._update_count(); });
        this.$pool.append($tag);
    },

    _fetch_by_filter: function () {
        var me = this;
        var customer  = me.f_customer.get_value();
        var from_date = me.f_from.get_value();
        var to_date   = me.f_to.get_value();
        var company   = me.f_company.get_value();

        if (!customer && !from_date && !to_date) {
            frappe.msgprint(__("Please set at least Customer, From Date, or To Date."));
            return;
        }

        var filters = { docstatus: 1 };
        if (customer)  filters.customer = customer;
        if (company)   filters.company  = company;
        if (from_date && to_date)  filters.posting_date = ["between", [from_date, to_date]];
        else if (from_date)        filters.posting_date = [">=", from_date];
        else if (to_date)          filters.posting_date = ["<=", to_date];

        frappe.call({
            method: "frappe.client.get_list",
            args: { doctype: "Sales Invoice", filters: filters,
                    fields: ["name"], limit_page_length: 500 },
            freeze: true, freeze_message: __("Fetching invoices..."),
            callback: function (r) {
                if (!r.message || !r.message.length) {
                    frappe.msgprint(__("No submitted invoices found for the given filters."));
                    return;
                }
                var added = 0;
                $.each(r.message, function (_, row) {
                    if (!me.$pool.find('[data-inv="' + row.name + '"]').length) {
                        me._append_tag(row.name);
                        added++;
                    }
                });
                me._update_count();
                frappe.show_alert({ message: added + " invoices added.", indicator: "green" });
            },
        });
    },

    _update_count: function () {
        var n = this.$pool.find(".bp-tag").length;
        this.$count_label.text(n + " invoice" + (n === 1 ? "" : "s") + " selected");
    },

    // STEP 2 - ITEM GROUP OVERRIDE
    _build_step2: function () {
        var me = this;
        var $c = $('<div class="bp-card"></div>').appendTo(this.$wrap);
        $c.append('<div class="bp-card-title">Step 2 - Item Group Override</div>');
        $c.append(
            '<div class="bp-card-desc">Map item codes to new item groups. Only matching line ' +
            'items will be updated. Leave empty to skip item group changes.</div>'
        );
        var $tbl = $(
            '<table class="bp-table"><thead><tr>' +
            '<th style="min-width:220px">Item Code</th>' +
            '<th style="min-width:220px">New Item Group</th>' +
            '<th></th>' +
            '</tr></thead><tbody></tbody></table>'
        ).appendTo($c);
        this.$ig_tbody = $tbl.find("tbody");
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c)
            .on("click", function () { me._add_ig_row(); });
    },

    _add_ig_row: function () {
        var me = this;
        var $tr = $("<tr></tr>").appendTo(me.$ig_tbody);
        var $td1 = $("<td></td>").appendTo($tr);
        var ic = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "ic_" + frappe.utils.get_random(6),
                  options: "Item", label: "", placeholder: "Item Code" },
            parent: $("<div></div>").appendTo($td1), render_input: true,
        });
        ic.refresh(); $tr.data("ic", ic);

        var $td2 = $("<td></td>").appendTo($tr);
        var ig = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "ig_" + frappe.utils.get_random(6),
                  options: "Item Group", label: "", placeholder: "New Item Group" },
            parent: $("<div></div>").appendTo($td2), render_input: true,
        });
        ig.refresh(); $tr.data("ig", ig);

        $("<td></td>").appendTo($tr).append(
            $('<button class="bp-rm-btn">x</button>')
                .on("click", function () { $tr.remove(); })
        );
    },

    // STEP 3 - SALES TEAM OVERRIDE
    // Uses plain <select> populated from get_all_sales_persons() to
    // bypass the Employee link permission filter.
    _build_step3: function () {
        var me = this;
        var $c = $('<div class="bp-card"></div>').appendTo(this.$wrap);
        $c.append('<div class="bp-card-title">Step 3 - Sales Team Override</div>');
        $c.append(
            '<div class="bp-card-desc">These rows will REPLACE the existing sales team on every ' +
            'selected invoice. Leave empty to keep each invoice\'s existing sales team unchanged.</div>'
        );
        var $tbl = $(
            '<table class="bp-table"><thead><tr>' +
            '<th style="min-width:240px">Sales Person</th>' +
            '<th style="min-width:120px">Allocated %</th>' +
            '<th></th>' +
            '</tr></thead><tbody></tbody></table>'
        ).appendTo($c);
        this.$st_tbody = $tbl.find("tbody");
        $c.append('<div class="bp-pct-note">Total allocated % should equal 100.</div>');
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c)
            .on("click", function () { me._add_st_row(); });
    },

    // Build one sales team row with a plain <select> instead of a
    // Frappe Link control - bypasses Employee-based permission filter.
    _add_st_row: function () {
        var me = this;
        var $tr = $("<tr></tr>").appendTo(me.$st_tbody);

        var $td1 = $("<td></td>").appendTo($tr);
        var $sel = $('<select class="bp-sp-select"></select>');
        $sel.append($('<option value="">-- Select Sales Person --</option>'));
        $.each(me.all_sales_persons, function (_, sp) {
            var label = sp.name + (sp.sales_person_name && sp.sales_person_name !== sp.name
                ? " (" + sp.sales_person_name + ")" : "");
            $sel.append($("<option></option>").val(sp.name).text(label));
        });
        $td1.append($sel);
        $tr.data("sp_sel", $sel);

        var $td2 = $("<td></td>").appendTo($tr);
        var $pct = $('<input type="number" class="form-control" min="0" max="100" step="0.01" value="100"/>')
            .appendTo($td2);
        $tr.data("pct", $pct);

        $("<td></td>").appendTo($tr).append(
            $('<button class="bp-rm-btn">x</button>')
                .on("click", function () { $tr.remove(); })
        );
    },

    // APPLY BUTTON + PROGRESS
    _build_apply: function () {
        var me = this;
        this.$apply_wrap = $('<div style="margin-bottom:24px;"></div>').appendTo(this.$wrap);
        $('<button class="btn btn-primary btn-lg">Apply to All Selected Invoices</button>')
            .appendTo(this.$apply_wrap)
            .on("click", function () { me._validate_and_run(); });
        this.$progress_wrap = $('<div style="display:none;margin-top:12px;"></div>')
            .appendTo(this.$apply_wrap);
        this.$progress_wrap.html(
            '<div class="bp-prog-label" id="bp-prog-label">Processing...</div>' +
            '<div class="bp-progress-track"><div class="bp-progress-bar" style="width:0%"></div></div>'
        );
    },

    _build_results: function () {
        this.$results = $('<div></div>').appendTo(this.$wrap);
    },

    _validate_and_run: function () {
        var me = this;
        var invoice_names = [];
        me.$pool.find(".bp-tag").each(function () {
            invoice_names.push($(this).attr("data-inv"));
        });
        if (!invoice_names.length) {
            frappe.msgprint(__("Please add at least one invoice.")); return;
        }

        var item_group_map = {};
        me.$ig_tbody.find("tr").each(function () {
            var $tr = $(this);
            var ic_val = $tr.data("ic") ? $tr.data("ic").get_value() : "";
            var ig_val = $tr.data("ig") ? $tr.data("ig").get_value() : "";
            if (ic_val && ig_val) item_group_map[ic_val] = ig_val;
        });

        // Read sales person from <select> instead of Frappe link control
        var sales_team = [], total_pct = 0;
        me.$st_tbody.find("tr").each(function () {
            var $tr  = $(this);
            var $sel = $tr.data("sp_sel");
            var sp_val  = $sel ? $sel.val() : "";
            var pct_val = parseFloat($tr.data("pct").val()) || 0;
            if (sp_val) {
                sales_team.push({ sales_person: sp_val, allocated_percentage: pct_val });
                total_pct += pct_val;
            }
        });

        if (!Object.keys(item_group_map).length && !sales_team.length) {
            frappe.msgprint(__("Please configure at least one change in Step 2 or Step 3."));
            return;
        }

        var do_run = function () { me._run(invoice_names, sales_team, item_group_map); };

        if (sales_team.length && Math.abs(total_pct - 100) > 0.1) {
            frappe.confirm(
                __("Sales team total is {0}%, not 100%. Proceed anyway?", [total_pct.toFixed(2)]),
                do_run
            );
            return;
        }

        frappe.confirm(
            __("Apply changes to {0} invoice(s)? This cannot be undone.", [invoice_names.length]),
            do_run
        );
    },

    _run: function (invoice_names, sales_team, item_group_map) {
        var me = this;
        me.$results.empty();
        me.$progress_wrap.show();
        me.$progress_wrap.find(".bp-progress-bar").css("width", "0%");
        $("#bp-prog-label").text("Processing " + invoice_names.length + " invoices...");

        frappe.call({
            method: BULK_METHOD_BASE + "bulk_patch_invoices",
            args: {
                invoice_names:  JSON.stringify(invoice_names),
                sales_team:     JSON.stringify(sales_team),
                item_group_map: JSON.stringify(item_group_map),
            },
            freeze: true,
            freeze_message: __("Patching {0} invoices...", [invoice_names.length]),
            callback: function (r) {
                me.$progress_wrap.find(".bp-progress-bar").css("width", "100%");
                if (!r.message) return;
                var res = r.message;
                $("#bp-prog-label").text(
                    res.success_count + " updated, " +
                    res.skip_count    + " skipped, " +
                    res.errors.length + " errors."
                );
                frappe.show_alert({
                    message: __(
                        "{0} invoice(s) updated, {1} skipped, {2} error(s).",
                        [res.success_count, res.skip_count, res.errors.length]
                    ),
                    indicator: res.errors.length ? "orange" : "green",
                });
                me._render_results(res);
            },
        });
    },

    _render_results: function (res) {
        var $card = $('<div class="bp-card"></div>').appendTo(this.$results);
        $card.append('<div class="bp-card-title">Results</div>');
        var $sum = $('<div class="bp-summary"></div>').appendTo($card);
        $sum.append('<div class="bp-summary-item"><span class="bp-summary-label">Updated</span>' +
            '<span class="bp-summary-val" style="color:var(--green)">' + res.success_count + '</span></div>');
        $sum.append('<div class="bp-summary-item"><span class="bp-summary-label">No Change</span>' +
            '<span class="bp-summary-val" style="color:var(--text-muted)">' + res.skip_count + '</span></div>');
        $sum.append('<div class="bp-summary-item"><span class="bp-summary-label">Errors</span>' +
            '<span class="bp-summary-val" style="color:var(--red)">' + res.errors.length + '</span></div>');
        $sum.append('<div class="bp-summary-item"><span class="bp-summary-label">Total</span>' +
            '<span class="bp-summary-val">' + (res.success_count + res.skip_count + res.errors.length) + '</span></div>');

        var $tbl = $(
            '<table class="bp-result-table"><thead><tr>' +
            '<th>Invoice</th><th>Customer</th><th>Date</th>' +
            '<th>Grand Total</th><th>Status</th><th>Changes</th>' +
            '</tr></thead><tbody></tbody></table>'
        ).appendTo($card);
        var $tbody = $tbl.find("tbody");

        $.each(res.results, function (_, row) {
            var tag = row.status === "success"
                ? '<span class="tag-ok">Updated</span>'
                : '<span class="tag-skip">No Change</span>';
            var detail = (row.changes && row.changes.length)
                ? row.changes.map(function (c) { return frappe.utils.escape_html(c); }).join("<br>")
                : "-";
            var $tr = $("<tr></tr>").appendTo($tbody);
            $tr.append('<td><a href="/app/sales-invoice/' + frappe.utils.escape_html(row.invoice) +
                '" target="_blank">' + frappe.utils.escape_html(row.invoice) + '</a></td>');
            $tr.append("<td>" + frappe.utils.escape_html(row.customer || "") + "</td>");
            $tr.append("<td>" + frappe.utils.escape_html(row.posting_date || "") + "</td>");
            $tr.append("<td>" + format_currency(row.grand_total) + "</td>");
            $tr.append("<td>" + tag + "</td>");
            $tr.append('<td style="font-size:11px;">' + detail + "</td>");
        });

        $.each(res.errors, function (_, row) {
            var $tr = $("<tr></tr>").appendTo($tbody);
            $tr.append('<td>' + frappe.utils.escape_html(row.invoice) + '</td>');
            $tr.append('<td colspan="3"></td>');
            $tr.append('<td><span class="tag-err">Error</span></td>');
            $tr.append('<td style="font-size:11px;color:var(--red);">' +
                frappe.utils.escape_html(row.error) + "</td>");
        });
    },
});