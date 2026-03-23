frappe.pages["patch-dn-bulk"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Bulk Patch Delivery Note Fields",
        single_column: true,
    });
    new PatchDNBulk(page, wrapper);
};

var PDB_METHOD_BASE = "mdpl_custom_report.mdpl_custom_report.page.patch_dn_single.patch_dn_single.";

var PatchDNBulk = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".pdb-wrap { max-width: 1020px; margin: 24px auto; padding: 0 16px; }" +
            ".pdb-search-row { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 20px; }" +
            ".pdb-search-row .frappe-control { flex: 1; margin: 0; }" +
            ".pdb-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 20px 24px; margin-bottom: 20px; }" +
            ".pdb-card-title { font-size: 13px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 14px; }" +
            ".pdb-table { width: 100%; border-collapse: collapse; margin-top: 4px; }" +
            ".pdb-table th { font-size: 11px; font-weight: 600; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.04em; padding: 6px 8px;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left; }" +
            ".pdb-table td { padding: 7px 8px; border-bottom: 1px solid var(--border-color);" +
            "  vertical-align: middle; font-size: 13px; }" +
            ".pdb-table tr:last-child td { border-bottom: none; }" +
            ".pdb-table input.form-control { height: 28px; font-size: 12px; padding: 2px 8px; }" +
            ".pdb-table .link-btn { display: none !important; }" +
            ".pdb-remove-btn { color: var(--red); cursor: pointer; font-size: 14px;" +
            "  padding: 2px 6px; background: none; border: none; }" +
            ".pdb-remove-btn:hover { opacity:.7; }" +
            ".pdb-pct-warning { font-size: 11px; color: var(--text-muted); margin-top: 6px; }" +
            ".pdb-dn-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px;" +
            "  background: var(--bg-blue); color: var(--text-on-blue); border-radius: 12px;" +
            "  font-size: 12px; margin: 3px; }" +
            ".pdb-dn-tag .rm { cursor: pointer; font-size: 14px; margin-left: 2px; opacity:.7; }" +
            ".pdb-dn-tag .rm:hover { opacity:1; }" +
            ".pdb-dn-pool { min-height: 40px; padding: 6px; border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius); margin-bottom: 10px; flex-wrap: wrap; display:flex; }" +
            ".pdb-progress { margin: 12px 0; }" +
            ".pdb-progress-bar { height: 6px; border-radius: 3px; background: var(--primary); transition: width .3s; }" +
            ".pdb-progress-track { height: 6px; border-radius: 3px; background: var(--border-color); }" +
            ".pdb-result-table { width:100%; border-collapse:collapse; font-size:12px; }" +
            ".pdb-result-table th, .pdb-result-table td { padding:5px 8px;" +
            "  border-bottom:1px solid var(--border-color); text-align:left; }" +
            ".pdb-result-table th { font-weight:600; color:var(--text-muted); }" +
            ".tag-success { color: var(--green); font-weight:600; }" +
            ".tag-skip { color: var(--text-muted); }" +
            ".tag-error { color: var(--red); font-weight:600; }"
        );

        this.$wrap = $('<div class="pdb-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        this._build();
    },

    _build: function () {
        var me = this;
        var $w = this.$wrap;

        // ---- Step 1: DN selection ----
        var $c1 = $('<div class="pdb-card"></div>').appendTo($w);
        $c1.append('<div class="pdb-card-title">Step 1 - Select Delivery Notes</div>');

        var $add_row = $('<div class="pdb-search-row"></div>').appendTo($c1);
        this.dn_field = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "dn_link", options: "Delivery Note",
                  label: "Add Delivery Note", filters: { docstatus: 1 },
                  placeholder: "Search and add delivery note..." },
            parent: $add_row, render_input: true,
        });
        this.dn_field.refresh();
        $('<button class="btn btn-default btn-sm" style="height:32px;white-space:nowrap">Add</button>')
            .appendTo($add_row).on("click", function () { me._add_dn(); });
        $(this.dn_field.input).on("keydown", function (e) { if (e.which === 13) me._add_dn(); });

        // Filter row
        var $fr = $('<div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;"></div>')
            .appendTo($c1);
        this.cust_field = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "cust", options: "Customer",
                  label: "Filter by Customer", placeholder: "Optional" },
            parent: $fr, render_input: true,
        });
        this.cust_field.refresh();
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
        $('<button class="btn btn-default btn-sm" style="height:32px;white-space:nowrap">Fetch DNs</button>')
            .appendTo($fr).on("click", function () { me._fetch_by_filter(); });

        this.$pool = $('<div class="pdb-dn-pool"></div>').appendTo($c1);
        $c1.append(
            '<div style="display:flex;justify-content:space-between;align-items:center;">' +
            '<span id="pdb-count" style="font-size:12px;color:var(--text-muted);">0 delivery notes selected</span>' +
            '<button class="btn btn-xs btn-default" id="pdb-clear">Clear All</button></div>'
        );
        $c1.find("#pdb-clear").on("click", function () { me.$pool.empty(); me._update_count(); });

        // ---- Step 2: Item Group map ----
        var $c2 = $('<div class="pdb-card"></div>').appendTo($w);
        $c2.append(
            '<div class="pdb-card-title">Step 2 - Item Group Override</div>' +
            '<div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">' +
            'Map item codes to new item groups. Leave empty to skip item group changes.</div>'
        );
        var $ig_tbl = $(
            '<table class="pdb-table" id="pdb-ig-table"><thead><tr>' +
            "<th style='min-width:220px'>Item Code</th>" +
            "<th style='min-width:220px'>New Item Group</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo($c2);
        this.$ig_tbody = $ig_tbl.find("tbody");
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c2).on("click", function () { me._add_ig_row(); });

        // ---- Step 3: Sales Team ----
        var $c3 = $('<div class="pdb-card"></div>').appendTo($w);
        $c3.append(
            '<div class="pdb-card-title">Step 3 - Sales Team Override</div>' +
            '<div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">' +
            'These rows will REPLACE the existing sales team on every selected Delivery Note.' +
            ' Leave empty to keep existing sales team unchanged.</div>'
        );
        var $st_tbl = $(
            '<table class="pdb-table" id="pdb-st-table"><thead><tr>' +
            "<th style='min-width:220px'>Sales Person</th><th>Allocated %</th><th></th>" +
            "</tr></thead><tbody></tbody></table>"
        ).appendTo($c3);
        this.$st_tbody = $st_tbl.find("tbody");
        $c3.append('<div class="pdb-pct-warning">Total allocated % should equal 100.</div>');
        $('<button class="btn btn-xs btn-default" style="margin-top:10px;">+ Add Row</button>')
            .appendTo($c3).on("click", function () { me._add_st_row(); });

        // ---- Apply ----
        var $apply = $('<div style="margin-bottom:32px;"></div>').appendTo($w);
        $('<button class="btn btn-primary btn-lg">Apply to All Selected Delivery Notes</button>')
            .appendTo($apply).on("click", function () { me._do_bulk(); });

        this.$progress = $('<div class="pdb-progress" style="display:none;"></div>').appendTo($apply);
        this.$progress.html(
            '<div class="pdb-progress-track"><div class="pdb-progress-bar" style="width:0%"></div></div>' +
            '<div id="pdb-prog-label" style="font-size:12px;color:var(--text-muted);margin-top:4px;"></div>'
        );

        this.$result = $('<div></div>').appendTo($w);
    },

    _add_dn: function () {
        var me = this;
        var dn = (this.dn_field.get_value() || "").trim();
        if (!dn) return;
        if (me.$pool.find('[data-dn="' + dn + '"]').length) {
            frappe.show_alert({ message: dn + " already added.", indicator: "orange" }); return;
        }
        var $tag = $('<span class="pdb-dn-tag"></span>').attr("data-dn", dn).text(dn);
        $('<span class="rm">x</span>').appendTo($tag)
            .on("click", function () { $tag.remove(); me._update_count(); });
        me.$pool.append($tag);
        me.dn_field.set_value("");
        me._update_count();
    },

    _fetch_by_filter: function () {
        var me = this;
        var filters = { docstatus: 1 };
        var cust      = me.cust_field.get_value();
        var from_date = me.from_date.get_value();
        var to_date   = me.to_date.get_value();

        if (cust) filters.customer = cust;
        if (from_date && to_date) filters.posting_date = ["between", [from_date, to_date]];
        else if (from_date) filters.posting_date = [">=", from_date];
        else if (to_date)   filters.posting_date = ["<=", to_date];

        if (!cust && !from_date && !to_date) {
            frappe.msgprint(__("Please set at least one filter.")); return;
        }

        frappe.call({
            method: "frappe.client.get_list",
            args: { doctype: "Delivery Note", filters: filters, fields: ["name"], limit_page_length: 500 },
            freeze: true, freeze_message: __("Fetching delivery notes..."),
            callback: function (r) {
                if (!r.message || !r.message.length) {
                    frappe.msgprint(__("No submitted Delivery Notes found.")); return;
                }
                var added = 0;
                $.each(r.message, function (_, row) {
                    if (!me.$pool.find('[data-dn="' + row.name + '"]').length) {
                        var $tag = $('<span class="pdb-dn-tag"></span>').attr("data-dn", row.name).text(row.name);
                        $('<span class="rm">x</span>').appendTo($tag)
                            .on("click", function () { $tag.remove(); me._update_count(); });
                        me.$pool.append($tag);
                        added++;
                    }
                });
                me._update_count();
                frappe.show_alert({ message: __("{0} delivery notes added.", [added]), indicator: "green" });
            },
        });
    },

    _update_count: function () {
        var n = this.$pool.find(".pdb-dn-tag").length;
        $("#pdb-count").text(n + " delivery note" + (n === 1 ? "" : "s") + " selected");
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
            $('<button class="pdb-remove-btn">x</button>').on("click", function () { $tr.remove(); })
        );
    },

    _add_st_row: function () {
        var me = this;
        var $tr = $("<tr></tr>").appendTo(me.$st_tbody);
        var $td_sp = $("<td></td>").appendTo($tr);
        var sp = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "sp_" + frappe.utils.get_random(6),
                  options: "Sales Person", label: "", placeholder: "Sales Person" },
            parent: $("<div></div>").appendTo($td_sp), render_input: true,
        });
        sp.refresh(); $tr.data("sp_ctrl", sp);
        var $td_pct = $("<td></td>").appendTo($tr);
        $('<input type="number" class="form-control" min="0" max="100" step="0.01" value="100"/>')
            .appendTo($td_pct).each(function () { $tr.data("pct_input", $(this)); });
        $("<td></td>").appendTo($tr).append(
            $('<button class="pdb-remove-btn">x</button>').on("click", function () { $tr.remove(); })
        );
    },

    _do_bulk: function () {
        var me = this;
        var dn_names = [];
        me.$pool.find(".pdb-dn-tag").each(function () { dn_names.push($(this).attr("data-dn")); });
        if (!dn_names.length) { frappe.msgprint(__("Please add at least one Delivery Note.")); return; }

        var item_group_map = {};
        me.$ig_tbody.find("tr").each(function () {
            var $tr = $(this);
            var ic = $tr.data("ic_ctrl") ? $tr.data("ic_ctrl").get_value() : "";
            var ig = $tr.data("ig_ctrl") ? $tr.data("ig_ctrl").get_value() : "";
            if (ic && ig) item_group_map[ic] = ig;
        });

        var sales_team = [], total_pct = 0;
        me.$st_tbody.find("tr").each(function () {
            var $tr = $(this);
            var sp = $tr.data("sp_ctrl") ? $tr.data("sp_ctrl").get_value() : "";
            var pct = parseFloat($tr.data("pct_input").val()) || 0;
            if (sp) { sales_team.push({ sales_person: sp, allocated_percentage: pct }); total_pct += pct; }
        });

        if (!Object.keys(item_group_map).length && !sales_team.length) {
            frappe.msgprint(__("Please configure at least one change.")); return;
        }

        var _run = function () {
            me.$result.empty();
            me.$progress.show();
            me.$progress.find(".pdb-progress-bar").css("width", "0%");
            $("#pdb-prog-label").text("Processing...");

            frappe.call({
                method: PDB_METHOD_BASE + "bulk_patch_dns",
                args: {
                    dn_names: JSON.stringify(dn_names),
                    sales_team: JSON.stringify(sales_team),
                    item_group_map: JSON.stringify(item_group_map),
                },
                freeze: true, freeze_message: __("Patching {0} delivery notes...", [dn_names.length]),
                callback: function (r) {
                    me.$progress.find(".pdb-progress-bar").css("width", "100%");
                    if (!r.message) return;
                    var res = r.message;
                    $("#pdb-prog-label").text(
                        res.success_count + " patched, " + res.skip_count + " skipped, " + res.errors.length + " errors."
                    );
                    frappe.show_alert({
                        message: __("{0} updated, {1} skipped, {2} errors.", [res.success_count, res.skip_count, res.errors.length]),
                        indicator: res.errors.length ? "orange" : "green",
                    });

                    var html = "<div class='pdb-card' style='margin-top:16px;'>" +
                               "<div class='pdb-card-title'>Bulk Patch Results</div>" +
                               "<table class='pdb-result-table'>" +
                               "<thead><tr><th>Delivery Note</th><th>Status</th><th>Details</th></tr></thead><tbody>";
                    $.each(res.results, function (_, row) {
                        var tag = row.status === "success"
                            ? '<span class="tag-success">Updated</span>'
                            : '<span class="tag-skip">No Changes</span>';
                        var detail = (row.changes || []).map(function (c) { return frappe.utils.escape_html(c); }).join("<br>") || "-";
                        html += "<tr><td>" + frappe.utils.escape_html(row.dn) + "</td><td>" + tag + "</td><td style='font-size:11px;'>" + detail + "</td></tr>";
                    });
                    $.each(res.errors, function (_, row) {
                        html += "<tr><td>" + frappe.utils.escape_html(row.dn) +
                                "</td><td><span class='tag-error'>Error</span></td>" +
                                "<td style='font-size:11px;color:var(--red);'>" + frappe.utils.escape_html(row.error) + "</td></tr>";
                    });
                    html += "</tbody></table></div>";
                    me.$result.html(html);
                },
            });
        };

        if (sales_team.length && Math.abs(total_pct - 100) > 0.1) {
            frappe.confirm(__("Sales team total is {0}%, not 100%. Proceed anyway?", [total_pct.toFixed(2)]), _run);
            return;
        }
        frappe.confirm(__("Apply changes to {0} Delivery Note(s)? This cannot be undone.", [dn_names.length]), _run);
    },
});