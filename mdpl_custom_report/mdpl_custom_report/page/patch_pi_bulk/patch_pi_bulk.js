frappe.pages["patch-pi-bulk"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Bulk Patch Purchase Invoice Fields",
        single_column: true,
    });
    new PatchPIBulk(page, wrapper);
};

var PIB_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_pi_single.patch_pi_single.";

var PatchPIBulk = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".pib2-wrap { max-width: 1020px; margin: 24px auto; padding: 0 16px; }" +
            ".pib2-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 20px; }" +
            ".pib2-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".pib2-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".pib2-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 14px; }" +
            ".pib2-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".pib2-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".pib2-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".pib2-table tr:last-child td { border-bottom: none; }" +
            ".pib2-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".pib2-table .link-btn { display: none !important; }" +
            ".pib2-remove-btn { color: var(--red); cursor: pointer; font-size: 14px;" +
            "  padding: 2px 6px; background: none; border: none; }" +
            ".pib2-remove-btn:hover { opacity:.7; }" +
            ".pib2-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px;" +
            "  background: var(--bg-blue); color: var(--text-on-blue); border-radius: 12px;" +
            "  font-size: 12px; margin: 3px; }" +
            ".pib2-tag .rm { cursor: pointer; font-size: 14px; margin-left: 2px; opacity:.7; }" +
            ".pib2-tag .rm:hover { opacity:1; }" +
            ".pib2-pool { min-height: 40px; padding: 6px; border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius); margin-bottom: 10px; flex-wrap: wrap; display:flex; }" +
            ".pib2-progress { margin: 12px 0; }" +
            ".pib2-progress-bar { height: 6px; border-radius: 3px; background: var(--primary); transition: width .3s; }" +
            ".pib2-progress-track { height: 6px; border-radius: 3px; background: var(--border-color); }" +
            ".pib2-result-table { width:100%; border-collapse:collapse; font-size:12px; }" +
            ".pib2-result-table th, .pib2-result-table td { padding:5px 8px;" +
            "  border-bottom:1px solid var(--border-color); text-align:left; }" +
            ".pib2-result-table th { font-weight:600; color:var(--text-muted); }" +
            ".tag-success { color: var(--green); font-weight:600; }" +
            ".tag-skip { color: var(--text-muted); }" +
            ".tag-error { color: var(--red); font-weight:600; }"
        );

        this.$wrap = $('<div class="pib2-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );
        this._build();
    },

    _build: function () {
        var me = this;
        var $w = this.$wrap;

        // Step 1 - Select PIs
        var $c1 = $('<div class="pib2-card"></div>').appendTo($w);
        $c1.append('<div class="pib2-card-title">Step 1 - Select Purchase Invoices</div>');

        var $add_row = $('<div class="pib2-search-row"></div>').appendTo($c1);
        this.pi_field = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "pi_link", options: "Purchase Invoice",
                  label: "Add Purchase Invoice", filters: { docstatus: 1 },
                  placeholder: "Search and add purchase invoice..." },
            parent: $add_row, render_input: true,
        });
        this.pi_field.refresh();
        $('<button class="btn btn-default btn-sm" style="height:32px;white-space:nowrap">Add</button>')
            .appendTo($add_row).on("click", function () { me._add_pi(); });
        $(this.pi_field.input).on("keydown", function (e) { if (e.which === 13) me._add_pi(); });

        // Filter row
        var $fr = $('<div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;"></div>').appendTo($c1);
        this.supp_field = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "supp", options: "Supplier",
                  label: "Filter by Supplier", placeholder: "Optional" },
            parent: $fr, render_input: true,
        });
        this.supp_field.refresh();
        this.from_date = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "from_dt", label: "From Date" },
            parent: $fr, render_input: true,
        });
        this.from_date.refresh();
        this.to_date = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "to_dt", label: "To Date" },
            parent: $fr, render_input: true,
        });
        this.to_date.refresh();
        $('<button class="btn btn-default btn-sm" style="height:32px;white-space:nowrap">Fetch PIs</button>')
            .appendTo($fr).on("click", function () { me._fetch_by_filter(); });

        this.$pool = $('<div class="pib2-pool"></div>').appendTo($c1);
        $c1.append(
            '<div style="display:flex;justify-content:space-between;align-items:center;">' +
            '<span id="pib2-count" style="font-size:12px;color:var(--text-muted);">0 purchase invoices selected</span>' +
            '<button class="btn btn-xs btn-default" id="pib2-clear">Clear All</button></div>'
        );
        $c1.find("#pib2-clear").on("click", function () { me.$pool.empty(); me._update_count(); });

        // Step 2 - Item Group map
        var $c2 = $('<div class="pib2-card"></div>').appendTo($w);
        $c2.append(
            '<div class="pib2-card-title">Step 2 - Item Group Override</div>' +
            '<div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">' +
            'Map item codes to new item groups. Leave empty to skip.</div>'
        );
        var $ig_tbl = $(
            '<table class="pib2-table"><thead><tr>' +
            "<th style='min-width:220px'>Item Code</th><th style='min-width:220px'>New Item Group</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo($c2);
        this.$ig_tbody = $ig_tbl.find("tbody");
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c2).on("click", function () { me._add_ig_row(); });

        // Step 3 - Cost Center map
        var $c3 = $('<div class="pib2-card"></div>').appendTo($w);
        $c3.append(
            '<div class="pib2-card-title">Step 3 - Cost Center Override</div>' +
            '<div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">' +
            'Map item codes to new cost centers. Leave empty to skip.</div>'
        );
        var $cc_tbl = $(
            '<table class="pib2-table"><thead><tr>' +
            "<th style='min-width:220px'>Item Code</th><th style='min-width:220px'>New Cost Center</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo($c3);
        this.$cc_tbody = $cc_tbl.find("tbody");
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c3).on("click", function () { me._add_cc_row(); });

        // Apply
        var $apply = $('<div style="margin-bottom:32px;"></div>').appendTo($w);
        $('<button class="btn btn-primary btn-lg">Apply to All Selected Purchase Invoices</button>')
            .appendTo($apply).on("click", function () { me._do_bulk(); });

        this.$progress = $('<div class="pib2-progress" style="display:none;"></div>').appendTo($apply);
        this.$progress.html(
            '<div class="pib2-progress-track"><div class="pib2-progress-bar" style="width:0%"></div></div>' +
            '<div id="pib2-prog-label" style="font-size:12px;color:var(--text-muted);margin-top:4px;"></div>'
        );
        this.$result = $('<div></div>').appendTo($w);
    },

    _add_pi: function () {
        var me = this;
        var pi = (this.pi_field.get_value() || "").trim();
        if (!pi) return;
        if (me.$pool.find('[data-pi="' + pi + '"]').length) {
            frappe.show_alert({ message: pi + " already added.", indicator: "orange" }); return;
        }
        var $tag = $('<span class="pib2-tag"></span>').attr("data-pi", pi).text(pi);
        $('<span class="rm">x</span>').appendTo($tag)
            .on("click", function () { $tag.remove(); me._update_count(); });
        me.$pool.append($tag);
        me.pi_field.set_value("");
        me._update_count();
    },

    _fetch_by_filter: function () {
        var me = this;
        var filters = { docstatus: 1 };
        var supp      = me.supp_field.get_value();
        var from_date = me.from_date.get_value();
        var to_date   = me.to_date.get_value();

        if (supp) filters.supplier = supp;
        if (from_date && to_date) filters.posting_date = ["between", [from_date, to_date]];
        else if (from_date) filters.posting_date = [">=", from_date];
        else if (to_date)   filters.posting_date = ["<=", to_date];

        if (!supp && !from_date && !to_date) {
            frappe.msgprint(__("Please set at least one filter.")); return;
        }
        frappe.call({
            method: "frappe.client.get_list",
            args: { doctype: "Purchase Invoice", filters: filters, fields: ["name"], limit_page_length: 500 },
            freeze: true, freeze_message: __("Fetching purchase invoices..."),
            callback: function (r) {
                if (!r.message || !r.message.length) {
                    frappe.msgprint(__("No submitted Purchase Invoices found.")); return;
                }
                var added = 0;
                $.each(r.message, function (_, row) {
                    if (!me.$pool.find('[data-pi="' + row.name + '"]').length) {
                        var $tag = $('<span class="pib2-tag"></span>').attr("data-pi", row.name).text(row.name);
                        $('<span class="rm">x</span>').appendTo($tag)
                            .on("click", function () { $tag.remove(); me._update_count(); });
                        me.$pool.append($tag);
                        added++;
                    }
                });
                me._update_count();
                frappe.show_alert({ message: __("{0} purchase invoices added.", [added]), indicator: "green" });
            },
        });
    },

    _update_count: function () {
        var n = this.$pool.find(".pib2-tag").length;
        $("#pib2-count").text(n + " purchase invoice" + (n === 1 ? "" : "s") + " selected");
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
        ic.refresh(); $tr.data("ic_ctrl", ic);
        var $td2 = $("<td></td>").appendTo($tr);
        var ig = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "ig_" + frappe.utils.get_random(6),
                  options: "Item Group", label: "", placeholder: "New Item Group" },
            parent: $("<div></div>").appendTo($td2), render_input: true,
        });
        ig.refresh(); $tr.data("ig_ctrl", ig);
        $("<td></td>").appendTo($tr).append(
            $('<button class="pib2-remove-btn">x</button>').on("click", function () { $tr.remove(); })
        );
    },

    _add_cc_row: function () {
        var me = this;
        var $tr = $("<tr></tr>").appendTo(me.$cc_tbody);
        var $td1 = $("<td></td>").appendTo($tr);
        var ic = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "ic_" + frappe.utils.get_random(6),
                  options: "Item", label: "", placeholder: "Item Code" },
            parent: $("<div></div>").appendTo($td1), render_input: true,
        });
        ic.refresh(); $tr.data("ic_ctrl", ic);
        var $td2 = $("<td></td>").appendTo($tr);
        var cc = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "cc_" + frappe.utils.get_random(6),
                  options: "Cost Center", label: "", placeholder: "New Cost Center" },
            parent: $("<div></div>").appendTo($td2), render_input: true,
        });
        cc.refresh(); $tr.data("cc_ctrl", cc);
        $("<td></td>").appendTo($tr).append(
            $('<button class="pib2-remove-btn">x</button>').on("click", function () { $tr.remove(); })
        );
    },

    _do_bulk: function () {
        var me = this;
        var pi_names = [];
        me.$pool.find(".pib2-tag").each(function () { pi_names.push($(this).attr("data-pi")); });
        if (!pi_names.length) { frappe.msgprint(__("Please add at least one Purchase Invoice.")); return; }

        var item_group_map = {};
        me.$ig_tbody.find("tr").each(function () {
            var $tr = $(this);
            var ic = $tr.data("ic_ctrl") ? $tr.data("ic_ctrl").get_value() : "";
            var ig = $tr.data("ig_ctrl") ? $tr.data("ig_ctrl").get_value() : "";
            if (ic && ig) item_group_map[ic] = ig;
        });

        var cost_center_map = {};
        me.$cc_tbody.find("tr").each(function () {
            var $tr = $(this);
            var ic = $tr.data("ic_ctrl") ? $tr.data("ic_ctrl").get_value() : "";
            var cc = $tr.data("cc_ctrl") ? $tr.data("cc_ctrl").get_value() : "";
            if (ic && cc) cost_center_map[ic] = cc;
        });

        if (!Object.keys(item_group_map).length && !Object.keys(cost_center_map).length) {
            frappe.msgprint(__("Please configure at least one change (Item Group or Cost Center).")); return;
        }

        frappe.confirm(
            __("Apply changes to {0} Purchase Invoice(s)? This cannot be undone.", [pi_names.length]),
            function () {
                me.$result.empty();
                me.$progress.show();
                me.$progress.find(".pib2-progress-bar").css("width", "0%");
                $("#pib2-prog-label").text("Processing...");

                frappe.call({
                    method: PIB_METHOD_BASE + "bulk_patch_pis",
                    args: {
                        pi_names: JSON.stringify(pi_names),
                        item_group_map: JSON.stringify(item_group_map),
                        cost_center_map: JSON.stringify(cost_center_map),
                    },
                    freeze: true, freeze_message: __("Patching {0} purchase invoices...", [pi_names.length]),
                    callback: function (r) {
                        me.$progress.find(".pib2-progress-bar").css("width", "100%");
                        if (!r.message) return;
                        var res = r.message;
                        $("#pib2-prog-label").text(
                            res.success_count + " patched, " + res.skip_count + " skipped, " + res.errors.length + " errors."
                        );
                        frappe.show_alert({
                            message: __("{0} updated, {1} skipped, {2} errors.", [res.success_count, res.skip_count, res.errors.length]),
                            indicator: res.errors.length ? "orange" : "green",
                        });

                        var html = "<div class='pib2-card' style='margin-top:16px;'>" +
                                   "<div class='pib2-card-title'>Bulk Patch Results</div>" +
                                   "<table class='pib2-result-table'>" +
                                   "<thead><tr><th>Purchase Invoice</th><th>Status</th><th>Details</th></tr></thead><tbody>";
                        $.each(res.results, function (_, row) {
                            var tag = row.status === "success"
                                ? '<span class="tag-success">Updated</span>'
                                : '<span class="tag-skip">No Changes</span>';
                            var detail = (row.changes || []).map(function (c) { return frappe.utils.escape_html(c); }).join("<br>") || "-";
                            html += "<tr><td>" + frappe.utils.escape_html(row.pi) + "</td><td>" + tag + "</td><td style='font-size:11px;'>" + detail + "</td></tr>";
                        });
                        $.each(res.errors, function (_, row) {
                            html += "<tr><td>" + frappe.utils.escape_html(row.pi) +
                                    "</td><td><span class='tag-error'>Error</span></td>" +
                                    "<td style='font-size:11px;color:var(--red);'>" + frappe.utils.escape_html(row.error) + "</td></tr>";
                        });
                        html += "</tbody></table></div>";
                        me.$result.html(html);
                    },
                });
            }
        );
    },
});
