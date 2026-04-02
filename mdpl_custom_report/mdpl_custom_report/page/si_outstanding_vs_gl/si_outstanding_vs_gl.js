frappe.pages["si-outstanding-vs-gl"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "SI Outstanding vs Customer Ledger",
        single_column: true,
    });
    new SIOutstandingReport(page, wrapper);
};

var SI_RPT_METHOD = "mdpl_custom_report.mdpl_custom_report.page.si_outstanding_vs_gl.si_outstanding_vs_gl.get_si_outstanding_vs_gl";

var SIOutstandingReport = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.all_data = [];
        this.current_filter = "all";
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".siovgl-wrap { max-width: 1280px; margin: 20px auto; padding: 0 16px; }" +
            ".siovgl-filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 20px; }" +
            ".siovgl-filters .frappe-control { margin: 0; }" +
            ".siovgl-cards { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 20px; }" +
            ".siovgl-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); padding: 16px 20px; }" +
            ".siovgl-card .lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing:.05em; margin-bottom: 6px; }" +
            ".siovgl-card .val { font-size: 24px; font-weight: 600; color: var(--text-color); }" +
            ".siovgl-card.red .val { color: var(--red-500,#e74c3c); }" +
            ".siovgl-card.amber .val { color: var(--yellow-500,#e67e22); }" +
            ".siovgl-card.green .val { color: var(--green-500,#27ae60); }" +
            ".siovgl-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); }" +
            ".siovgl-tab { padding: 8px 18px; font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent; color: var(--text-muted); background: none; border-top: none; border-left: none; border-right: none; }" +
            ".siovgl-tab.active { border-bottom-color: var(--primary); color: var(--primary); font-weight: 500; }" +
            ".siovgl-tab:hover { color: var(--text-color); }" +
            ".siovgl-tab .tab-count { display: inline-block; margin-left: 5px; font-size: 10px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 10px; padding: 0 6px; color: var(--text-muted); }" +
            ".siovgl-tab.active .tab-count { background: var(--primary); border-color: var(--primary); color: #fff; }" +
            ".siovgl-tbl-wrap { border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); overflow-x: auto; }" +
            ".siovgl-table { width: 100%; border-collapse: collapse; min-width: 960px; }" +
            ".siovgl-table th { padding: 8px 12px; font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em; border-bottom: 1px solid var(--border-color); text-align: left; background: var(--subtle-bg); white-space: nowrap; }" +
            ".siovgl-table th.num { text-align: right; }" +
            ".siovgl-table td { padding: 9px 12px; border-bottom: 1px solid var(--border-color); font-size: 13px; vertical-align: middle; }" +
            ".siovgl-table tr:last-child td { border-bottom: none; }" +
            ".siovgl-table tr:hover td { background: var(--hover-bg); }" +
            ".siovgl-table td.num { text-align: right; font-variant-numeric: tabular-nums; }" +
            ".siovgl-badge { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }" +
            ".siovgl-badge.neg  { background: var(--red-100,#fde8e8); color: var(--red-600,#c0392b); }" +
            ".siovgl-badge.warn { background: var(--yellow-100,#fef3cd); color: var(--yellow-700,#856404); }" +
            ".siovgl-badge.both { background: var(--red-100,#fde8e8); color: var(--red-700,#a93226); }" +
            ".siovgl-badge.ok   { background: var(--green-100,#d5f5e3); color: var(--green-700,#1e8449); }" +
            ".siovgl-cause { font-size: 11px; color: var(--text-muted); max-width: 300px; white-space: normal; line-height: 1.4; }" +
            ".siovgl-empty { text-align: center; padding: 48px; color: var(--text-muted); font-size: 13px; }"
        );

        this.$wrap = $('<div class="siovgl-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        this._make_filters();
        this._make_summary();
        this._make_tabs();
        this._make_table();
        // Auto-run on page load
        var me = this;
        setTimeout(function () { me.load_data(); }, 300);
    },

    _make_filters: function () {
        var me = this;
        var $f = $('<div class="siovgl-filters"></div>').appendTo(this.$wrap);

        this.customer_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "customer", options: "Customer",
                  label: "Customer", placeholder: "All customers" },
            parent: $f, render_input: true,
        });
        this.customer_ctrl.refresh();

        this.company_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Link", fieldname: "company", options: "Company",
                  label: "Company", placeholder: "All companies" },
            parent: $f, render_input: true,
        });
        this.company_ctrl.refresh();

        this.from_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "from_date", label: "From date" },
            parent: $f, render_input: true,
        });
        this.from_ctrl.set_value(frappe.datetime.add_months(frappe.datetime.get_today(), -6));
        this.from_ctrl.refresh();

        this.to_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "to_date", label: "To date" },
            parent: $f, render_input: true,
        });
        this.to_ctrl.set_value(frappe.datetime.get_today());
        this.to_ctrl.refresh();

        $('<button class="btn btn-primary btn-sm" style="height:32px">Run Report</button>')
            .appendTo($f)
            .on("click", function () { me.load_data(); });

        $('<button class="btn btn-default btn-sm" style="height:32px">Export CSV</button>')
            .appendTo($f)
            .on("click", function () { me.export_csv(); });

        // All-time toggle
        var $all_wrap = $('<div style="display:flex;align-items:center;gap:6px;height:32px;padding-top:20px"></div>').appendTo($f);
        this.$all_time = $('<input type="checkbox" id="siovgl-alltime" style="width:14px;height:14px;cursor:pointer">').appendTo($all_wrap);
        $('<label for="siovgl-alltime" style="font-size:12px;cursor:pointer;white-space:nowrap;color:var(--text-muted)">All time</label>').appendTo($all_wrap);
        this.$all_time.on("change", function () {
            var checked = $(this).prop("checked");
            me.from_ctrl.$input.prop("disabled", checked);
            me.to_ctrl.$input.prop("disabled", checked);
            if (checked) {
                me.from_ctrl.set_value("");
                me.to_ctrl.set_value("");
            } else {
                me.from_ctrl.set_value(frappe.datetime.add_months(frappe.datetime.get_today(), -6));
                me.to_ctrl.set_value(frappe.datetime.get_today());
            }
        });
    },

    _make_summary: function () {
        this.$cards = $('<div class="siovgl-cards"></div>').appendTo(this.$wrap);
        this.$cards.html(
            this._card("Total Invoices Checked", "c-total", "") +
            this._card("Negative Outstanding",   "c-neg",   "red") +
            this._card("Ledger Mismatch",         "c-mis",   "amber") +
            this._card("Clean Invoices",          "c-ok",    "green")
        );
    },

    _card: function (label, id, cls) {
        return '<div class="siovgl-card ' + (cls || "") + '">' +
               '<div class="lbl">' + label + '</div>' +
               '<div class="val" id="' + id + '">-</div></div>';
    },

    _make_tabs: function () {
        var me = this;
        this.$tabs = $('<div class="siovgl-tabs"></div>').appendTo(this.$wrap);
        var defs = [
            { key: "all",      label: "All",                  count_key: "total"    },
            { key: "negative", label: "Negative Outstanding", count_key: "negative" },
            { key: "mismatch", label: "Ledger Mismatch",      count_key: "mismatch" },
            { key: "both",     label: "Neg + Mismatch",       count_key: "both"     },
            { key: "ok",       label: "Clean",                count_key: "ok"       },
        ];
        defs.forEach(function (d) {
            $('<button class="siovgl-tab ' + (d.key === "all" ? "active" : "") + '" data-key="' + d.key + '">' +
              d.label + '<span class="tab-count" id="tc-' + d.key + '">0</span></button>')
                .appendTo(me.$tabs)
                .on("click", function () {
                    me.$tabs.find(".siovgl-tab").removeClass("active");
                    $(this).addClass("active");
                    me.current_filter = d.key;
                    me._render_table();
                });
        });
    },

    _make_table: function () {
        this.$record_info = $('<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;" id="siovgl-rec-info"></div>').appendTo(this.$wrap);
        var $wrap = $('<div class="siovgl-tbl-wrap"></div>').appendTo(this.$wrap);
        $wrap.html(
            '<table class="siovgl-table">' +
            '<thead><tr>' +
            '<th>Sales Invoice</th>' +
            '<th>Customer</th>' +
            '<th>Posting Date</th>' +
            '<th class="num">Invoice Amount</th>' +
            '<th class="num">SI Outstanding</th>' +
            '<th class="num">GL Balance (Dr-Cr)</th>' +
            '<th class="num">Difference</th>' +
            '<th>Status</th>' +
            '<th>Likely Cause</th>' +
            '<th>Actions</th>' +
            '</tr></thead>' +
            '<tbody id="siovgl-tbody"><tr><td colspan="10" class="siovgl-empty">Run the report to load data.</td></tr></tbody>' +
            '</table>'
        );
    },

    load_data: function () {
        var me = this;
        var filters = {
            customer:  me.customer_ctrl.get_value() || "",
            company:   me.company_ctrl.get_value()  || "",
            from_date: me.from_ctrl.get_value()     || "",
            to_date:   me.to_ctrl.get_value()       || "",
        };

        frappe.call({
            method: SI_RPT_METHOD,
            args: { filters: filters },
            freeze: true,
            freeze_message: __("Fetching SI and GL data..."),
            callback: function (r) {
                if (!r.message) return;
                me.all_data = r.message.results || [];
                me._update_summary(r.message.summary || {});
                me._render_table();
            },
        });
    },

    _update_summary: function (summary) {
        $("#c-total").text(summary.total    || 0);
        $("#c-neg").text(summary.negative   || 0);
        $("#c-mis").text(summary.mismatch   || 0);
        $("#c-ok").text(summary.ok          || 0);

        $("#tc-all").text(summary.total     || 0);
        $("#tc-negative").text(summary.negative || 0);
        $("#tc-mismatch").text(summary.mismatch || 0);
        $("#tc-both").text(summary.both     || 0);
        $("#tc-ok").text(summary.ok         || 0);
    },

    _render_table: function () {
        var me = this;
        var f = me.current_filter;
        var rows = (me.all_data || []).filter(function (r) {
            if (f === "all")      return true;
            if (f === "negative") return r.status === "negative" || r.status === "both";
            if (f === "mismatch") return r.status === "mismatch" || r.status === "both";
            return r.status === f;
        });

        // Update record info
        var total = me.all_data ? me.all_data.length : 0;
        var label = f === "all"
            ? "Showing all " + total + " invoices in selected date range"
            : "Showing " + rows.length + " of " + total + " invoices in selected date range";
        $("#siovgl-rec-info").text(label);

        var $tbody = $("#siovgl-tbody");
        if (!rows.length) {
            $tbody.html('<tr><td colspan="10" class="siovgl-empty">No records match this filter.</td></tr>');
            return;
        }

        var html = rows.map(function (r) {
            var diff       = flt(r.difference, 2);
            var outst      = flt(r.outstanding, 2);
            var gl         = flt(r.gl_balance, 2);
            var diff_color  = diff !== 0 ? "color:var(--red-600,#c0392b);font-weight:600" : "";
            var outst_color = outst < 0  ? "color:var(--red-600,#c0392b);font-weight:600" : "";

            var badge_cls = r.status === "both"     ? "both" :
                            r.status === "negative" ? "neg"  :
                            r.status === "mismatch" ? "warn" : "ok";
            var badge_lbl = r.status === "both"     ? "Neg + Mismatch"       :
                            r.status === "negative" ? "Negative Outstanding" :
                            r.status === "mismatch" ? "Ledger Mismatch"      : "Clean";

            var actions = "";
            if (r.status !== "ok") {
                actions += '<a class="btn btn-xs btn-default" style="margin-right:4px" ' +
                           'href="/app/sales-invoice/' + encodeURIComponent(r.si_name) + '" target="_blank">Open SI</a>';
                if (r.status === "negative" || r.status === "both") {
                    actions += '<a class="btn btn-xs btn-default" ' +
                               'href="/app/payment-reconciliation" target="_blank">Reconcile</a>';
                }
            } else {
                actions = '<span style="color:var(--text-muted);font-size:11px">-</span>';
            }

            return "<tr>" +
                "<td><a href='/app/sales-invoice/" + encodeURIComponent(r.si_name) + "' target='_blank'>" + r.si_name + "</a></td>" +
                "<td>" + (r.customer || "") + "</td>" +
                "<td>" + r.posting_date + "</td>" +
                "<td class='num'>" + format_currency(r.grand_total) + "</td>" +
                "<td class='num' style='" + outst_color + "'>" + format_currency(r.outstanding) + "</td>" +
                "<td class='num'>" + format_currency(gl) + "</td>" +
                "<td class='num' style='" + diff_color + "'>" + format_currency(diff) + "</td>" +
                "<td><span class='siovgl-badge " + badge_cls + "'>" + badge_lbl + "</span></td>" +
                "<td><div class='siovgl-cause'>" + frappe.utils.escape_html(r.cause || "") + "</div></td>" +
                "<td>" + actions + "</td>" +
                "</tr>";
        }).join("");

        $tbody.html(html);
    },

    export_csv: function () {
        if (!this.all_data || !this.all_data.length) {
            frappe.msgprint(__("Run the report first."));
            return;
        }
        var headers = ["Sales Invoice","Customer","Posting Date","Grand Total",
                       "SI Outstanding","GL Balance","Difference","Status","Likely Cause"];
        var rows = this.all_data.map(function (r) {
            return [
                r.si_name, r.customer, r.posting_date, r.grand_total,
                r.outstanding, r.gl_balance, r.difference, r.status,
                '"' + (r.cause || "").replace(/"/g, '""') + '"'
            ].join(",");
        });
        var csv = headers.join(",") + "\n" + rows.join("\n");
        var blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        var a    = document.createElement("a");
        a.href     = URL.createObjectURL(blob);
        a.download = "si_outstanding_vs_gl_" + frappe.datetime.get_today() + ".csv";
        a.click();
        URL.revokeObjectURL(a.href);
    },
});

function flt(v, precision) {
    return parseFloat((parseFloat(v) || 0).toFixed(precision || 2));
}