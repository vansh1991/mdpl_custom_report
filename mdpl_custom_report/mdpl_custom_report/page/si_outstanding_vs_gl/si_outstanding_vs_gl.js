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

            // Filter bar
            ".siovgl-filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 20px; }" +
            ".siovgl-filters .frappe-control { margin: 0; }" +

            // Summary cards
            ".siovgl-cards { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 20px; }" +
            ".siovgl-card { background: var(--card-bg); border: 1px solid var(--border-color);" +
            "  border-radius: var(--border-radius-lg); padding: 16px 20px; }" +
            ".siovgl-card .lbl { font-size: 11px; color: var(--text-muted);" +
            "  text-transform: uppercase; letter-spacing:.05em; margin-bottom: 6px; }" +
            ".siovgl-card .val { font-size: 24px; font-weight: 600; color: var(--text-color); }" +
            ".siovgl-card.red  .val { color: var(--red-500,#e74c3c); }" +
            ".siovgl-card.amber .val { color: var(--yellow-500,#e67e22); }" +
            ".siovgl-card.green .val { color: var(--green-500,#27ae60); }" +

            // Tab strip
            ".siovgl-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); }" +
            ".siovgl-tab { padding: 8px 18px; font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent;" +
            "  color: var(--text-muted); background: none; border-top: none; border-left: none; border-right: none; }" +
            ".siovgl-tab.active { border-bottom-color: var(--primary); color: var(--primary); font-weight: 500; }" +
            ".siovgl-tab:hover { color: var(--text-color); }" +

            // Table
            ".siovgl-tbl-wrap { border: 1px solid var(--border-color); border-radius: var(--border-radius-lg); overflow-x: auto; }" +
            ".siovgl-table { width: 100%; border-collapse: collapse; min-width: 960px; }" +
            ".siovgl-table th { padding: 8px 12px; font-size: 11px; font-weight: 600;" +
            "  color: var(--text-muted); text-transform: uppercase; letter-spacing:.04em;" +
            "  border-bottom: 1px solid var(--border-color); text-align: left;" +
            "  background: var(--subtle-bg); white-space: nowrap; }" +
            ".siovgl-table th.num { text-align: right; }" +
            ".siovgl-table td { padding: 9px 12px; border-bottom: 1px solid var(--border-color);" +
            "  font-size: 13px; vertical-align: middle; }" +
            ".siovgl-table tr:last-child td { border-bottom: none; }" +
            ".siovgl-table tr:hover td { background: var(--hover-bg); }" +
            ".siovgl-table td.num { text-align: right; font-variant-numeric: tabular-nums; }" +

            // Badges
            ".siovgl-badge { display: inline-block; font-size: 11px; padding: 2px 8px;" +
            "  border-radius: 4px; font-weight: 500; }" +
            ".siovgl-badge.neg  { background: var(--red-100,#fde8e8); color: var(--red-600,#c0392b); }" +
            ".siovgl-badge.warn { background: var(--yellow-100,#fef3cd); color: var(--yellow-700,#856404); }" +
            ".siovgl-badge.both { background: var(--red-100,#fde8e8); color: var(--red-700,#a93226); }" +
            ".siovgl-badge.ok   { background: var(--green-100,#d5f5e3); color: var(--green-700,#1e8449); }" +

            // Cause text
            ".siovgl-cause { font-size: 11px; color: var(--text-muted); max-width: 300px;" +
            "  white-space: normal; line-height: 1.4; }" +

            // Empty
            ".siovgl-empty { text-align: center; padding: 48px; color: var(--text-muted); font-size: 13px; }"
        );

        this.$wrap = $('<div class="siovgl-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        this._make_filters();
        this._make_summary();
        this._make_tabs();
        this._make_table();
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
        this.from_ctrl.set_value(frappe.datetime.add_months(frappe.datetime.get_today(), -3));
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
    },

    _make_summary: function () {
        this.$cards = $('<div class="siovgl-cards"></div>').appendTo(this.$wrap);
        this.$cards.html(
            this._card("Total Invoices Checked", "c-total", "") +
            this._card("Negative Outstanding", "c-neg", "red") +
            this._card("Ledger Mismatch", "c-mis", "amber") +
            this._card("Clean Invoices", "c-ok", "green")
        );
    },

    _card: function (label, id, cls) {
        return '<div class="siovgl-card ' + cls + '">' +
               '<div class="lbl">' + label + '</div>' +
               '<div class="val" id="' + id + '">—</div></div>';
    },

    _make_tabs: function () {
        var me = this;
        var $tabs = $('<div class="siovgl-tabs"></div>').appendTo(this.$wrap);
        var defs = [
            { key: "all",      label: "All" },
            { key: "negative", label: "Negative Outstanding" },
            { key: "mismatch", label: "Ledger Mismatch" },
            { key: "both",     label: "Neg + Mismatch" },
            { key: "ok",       label: "Clean" },
        ];
        defs.forEach(function (d) {
            $('<button class="siovgl-tab ' + (d.key === "all" ? "active" : "") + '">' + d.label + '</button>')
                .appendTo($tabs)
                .on("click", function () {
                    $tabs.find(".siovgl-tab").removeClass("active");
                    $(this).addClass("active");
                    me.current_filter = d.key;
                    me._render_table();
                });
        });
    },

    _make_table: function () {
        var $wrap = $('<div class="siovgl-tbl-wrap"></div>').appendTo(this.$wrap);
        $wrap.html(
            '<table class="siovgl-table">' +
            '<thead><tr>' +
            '<th>Sales Invoice</th>' +
            '<th>Customer</th>' +
            '<th>Posting Date</th>' +
            '<th class="num">Invoice Amount</th>' +
            '<th class="num">SI Outstanding</th>' +
            '<th class="num">GL Balance (Dr−Cr)</th>' +
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
            company:   me.company_ctrl.get_value() || "",
            from_date: me.from_ctrl.get_value() || "",
            to_date:   me.to_ctrl.get_value() || "",
        };

        frappe.call({
            method: SI_RPT_METHOD,
            args: { filters: filters },
            freeze: true,
            freeze_message: __("Fetching SI and GL data..."),
            callback: function (r) {
                me.all_data = r.message || [];
                me._update_summary();
                me._render_table();
            },
        });
    },

    _update_summary: function () {
        var neg = 0, mis = 0, ok = 0;
        (this.all_data || []).forEach(function (r) {
            if (r.status === "both")     { neg++; mis++; }
            else if (r.status === "negative") neg++;
            else if (r.status === "mismatch") mis++;
            else ok++;
        });
        $("#c-total").text(this.all_data.length);
        $("#c-neg").text(neg);
        $("#c-mis").text(mis);
        $("#c-ok").text(ok);
    },

    _render_table: function () {
        var me = this;
        var f = me.current_filter;
        var rows = (me.all_data || []).filter(function (r) {
            if (f === "all") return true;
            return r.status === f;
        });

        var $tbody = $("#siovgl-tbody");
        if (!rows.length) {
            $tbody.html('<tr><td colspan="10" class="siovgl-empty">No records match this filter.</td></tr>');
            return;
        }

        var html = rows.map(function (r) {
            var diff    = flt(r.difference, 2);
            var outst   = flt(r.outstanding, 2);
            var gl      = flt(r.gl_balance, 2);
            var diff_color = diff !== 0 ? "color:var(--red-600,#c0392b);font-weight:600" : "";
            var outst_color = outst < 0 ? "color:var(--red-600,#c0392b);font-weight:600" : "";

            var badge_cls = r.status === "both"     ? "both" :
                            r.status === "negative" ? "neg"  :
                            r.status === "mismatch" ? "warn" : "ok";
            var badge_lbl = r.status === "both"     ? "Neg + Mismatch" :
                            r.status === "negative" ? "Negative Outstanding" :
                            r.status === "mismatch" ? "Ledger Mismatch"      : "Clean";

            var actions = "";
            if (r.status !== "ok") {
                actions +=
                    '<a class="btn btn-xs btn-default" style="margin-right:4px" ' +
                    'href="/app/sales-invoice/' + encodeURIComponent(r.si_name) + '" target="_blank">Open SI</a>';
                if (r.status === "negative" || r.status === "both") {
                    actions +=
                        '<a class="btn btn-xs btn-default" style="margin-right:4px" ' +
                        'href="/app/payment-reconciliation" target="_blank">Reconcile</a>';
                }
            } else {
                actions = '<span style="color:var(--text-muted);font-size:11px">—</span>';
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
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement("a");
        a.href     = url;
        a.download = "si_outstanding_vs_gl_" + frappe.datetime.get_today() + ".csv";
        a.click();
        URL.revokeObjectURL(url);
    },
});

function flt(v, precision) {
    return parseFloat((parseFloat(v) || 0).toFixed(precision || 2));
}
