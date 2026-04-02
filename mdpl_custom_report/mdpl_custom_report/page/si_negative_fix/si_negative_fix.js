frappe.pages["si-negative-fix"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Fix Negative SI Outstanding",
        single_column: true,
    });
    new SINegativeFix(page, wrapper);
};

var SINF_BASE = "mdpl_custom_report.mdpl_custom_report.page.si_negative_fix.si_negative_fix.";

var SINegativeFix = Class.extend({
    init: function (page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        this.si_data = null;
        this.make();
    },

    make: function () {
        var me = this;

        frappe.dom.set_style(
            ".sinf-wrap { max-width: 1100px; margin: 20px auto; padding: 0 16px; }" +

            // Search
            ".sinf-search { display:flex; gap:10px; align-items:flex-end; margin-bottom:20px; }" +
            ".sinf-search .frappe-control { flex:1; margin:0; }" +

            // Cards grid
            ".sinf-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }" +
            ".sinf-card { background:var(--card-bg); border:1px solid var(--border-color);" +
            "  border-radius:var(--border-radius-lg); padding:14px 18px; }" +
            ".sinf-card .lbl { font-size:11px; color:var(--text-muted); text-transform:uppercase;" +
            "  letter-spacing:.05em; margin-bottom:4px; }" +
            ".sinf-card .val { font-size:18px; font-weight:600; color:var(--text-color); }" +
            ".sinf-card.red .val { color:var(--red-500,#e74c3c); }" +
            ".sinf-card.green .val { color:var(--green-500,#27ae60); }" +
            ".sinf-card.amber .val { color:var(--yellow-600,#d97706); }" +

            // Section panels
            ".sinf-panel { background:var(--card-bg); border:1px solid var(--border-color);" +
            "  border-radius:var(--border-radius-lg); padding:18px 22px; margin-bottom:16px; }" +
            ".sinf-panel-title { font-size:12px; font-weight:600; color:var(--text-muted);" +
            "  text-transform:uppercase; letter-spacing:.05em; margin-bottom:14px; }" +

            // Table inside panels
            ".sinf-tbl { width:100%; border-collapse:collapse; font-size:13px; }" +
            ".sinf-tbl th { font-size:11px; font-weight:600; color:var(--text-muted);" +
            "  text-transform:uppercase; letter-spacing:.04em; padding:5px 10px;" +
            "  border-bottom:1px solid var(--border-color); text-align:left; }" +
            ".sinf-tbl td { padding:7px 10px; border-bottom:1px solid var(--border-color);" +
            "  vertical-align:middle; }" +
            ".sinf-tbl tr:last-child td { border-bottom:none; }" +
            ".sinf-tbl td.num { text-align:right; font-variant-numeric:tabular-nums; }" +
            ".sinf-tbl .neg { color:var(--red-500,#e74c3c); font-weight:600; }" +
            ".sinf-tbl .pos { color:var(--green-600,#16a34a); }" +

            // Badge
            ".sinf-badge { display:inline-block; font-size:11px; padding:2px 8px;" +
            "  border-radius:4px; font-weight:500; }" +
            ".sinf-badge.ret { background:var(--yellow-100,#fef3cd); color:var(--yellow-700,#854d0e); }" +
            ".sinf-badge.nor { background:var(--blue-100,#dbeafe); color:var(--blue-700,#1d4ed8); }" +

            // JE form
            ".sinf-je-form { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px; }" +
            ".sinf-je-form .frappe-control { margin:0; }" +
            ".sinf-alert { padding:12px 16px; border-radius:var(--border-radius);" +
            "  font-size:13px; margin-bottom:14px; }" +
            ".sinf-alert.info { background:var(--alert-bg-blue,#eff6ff);" +
            "  border:1px solid var(--alert-border-blue,#bfdbfe); color:var(--blue-700,#1d4ed8); }" +
            ".sinf-alert.warn { background:var(--alert-bg-warning,#fffbeb);" +
            "  border:1px solid var(--yellow-300,#fcd34d); color:var(--yellow-700,#854d0e); }" +
            ".sinf-alert.success { background:var(--alert-bg-success);" +
            "  border:1px solid var(--alert-border-success); color:var(--alert-text-success); }" +
            ".sinf-empty { color:var(--text-muted); font-size:12px; font-style:italic; padding:8px 0; }"
        );

        this.$wrap = $('<div class="sinf-wrap"></div>').appendTo(
            $(this.wrapper).find(".page-content")
        );

        // Search bar
        var $s = $('<div class="sinf-search"></div>').appendTo(this.$wrap);
        this.si_ctrl = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", fieldname: "si_name",
                options: "Sales Invoice", label: "Sales Invoice",
                filters: { docstatus: 1, outstanding_amount: ["<", 0] },
                placeholder: "Select a negative outstanding Sales Invoice...",
            },
            parent: $s, render_input: true,
        });
        this.si_ctrl.refresh();
        $('<button class="btn btn-primary btn-sm" style="height:32px">Investigate</button>')
            .appendTo($s)
            .on("click", function () { me.load(); });
        $(this.si_ctrl.input).on("keydown", function (e) { if (e.which === 13) me.load(); });

        // Dynamic content area
        this.$content = $('<div></div>').appendTo(this.$wrap);
    },

    load: function () {
        var me = this;
        var si = (this.si_ctrl.get_value() || "").trim();
        if (!si) { frappe.msgprint(__("Please select a Sales Invoice.")); return; }

        frappe.call({
            method: SINF_BASE + "get_si_investigation",
            args: { si_name: si },
            freeze: true, freeze_message: __("Investigating invoice..."),
            callback: function (r) {
                if (r.message) { me.si_data = r.message; me.render(r.message); }
            },
        });
    },

    render: function (d) {
        var me = this;
        me.$content.empty();

        // ── Summary cards ──────────────────────────────────────────
        var $cards = $('<div class="sinf-cards"></div>').appendTo(me.$content);
        $cards.html(
            me._card("Invoice Amount",  format_currency(d.grand_total),   d.grand_total < 0 ? "red" : "") +
            me._card("SI Outstanding",  format_currency(d.outstanding),   d.outstanding < 0 ? "red" : "green") +
            me._card("GL Balance",      format_currency(d.gl_balance),    d.gl_balance < 0 ? "amber" : "") +
            me._card("Difference",      format_currency(d.difference),    Math.abs(d.difference) > 0.5 ? "red" : "green")
        );

        // ── Invoice info panel ─────────────────────────────────────
        var $info = $('<div class="sinf-panel"></div>').appendTo(me.$content);
        var is_return_badge = d.is_return
            ? '<span class="sinf-badge ret">Return / Credit Note</span>'
            : '<span class="sinf-badge nor">Regular Invoice</span>';
        var return_against = d.return_against
            ? '<br><span style="font-size:12px;color:var(--text-muted)">Return against: <a href="/app/sales-invoice/' +
              encodeURIComponent(d.return_against) + '" target="_blank">' + d.return_against + '</a></span>'
            : "";

        $info.html(
            '<div class="sinf-panel-title">Invoice Details</div>' +
            '<table class="sinf-tbl">' +
            '<tr><td style="width:180px;color:var(--text-muted)">Customer</td><td><b>' + d.customer + '</b></td>' +
            '    <td style="width:180px;color:var(--text-muted)">Posting Date</td><td>' + d.posting_date + '</td></tr>' +
            '<tr><td style="color:var(--text-muted)">Receivable Account</td><td>' + d.debit_to + '</td>' +
            '    <td style="color:var(--text-muted)">Company</td><td>' + d.company + '</td></tr>' +
            '<tr><td style="color:var(--text-muted)">Invoice Type</td><td>' + is_return_badge + return_against + '</td>' +
            '    <td style="color:var(--text-muted)">Status</td><td>' + d.status + '</td></tr>' +
            '</table>'
        );

        // ── GL Entries ─────────────────────────────────────────────
        me._panel(me.$content, "GL Entries for this Voucher", me._gl_table(d.gl_entries));

        // ── Payment Entries ────────────────────────────────────────
        me._panel(me.$content, "Linked Payment Entries", me._pe_table(d.payment_entries));

        // ── Journal Entries ────────────────────────────────────────
        me._panel(me.$content, "Linked Journal Entries", me._je_table(d.journal_entries));

        // ── Credit Notes ───────────────────────────────────────────
        me._panel(me.$content, "Linked Credit Notes / Returns", me._cn_table(d.credit_notes));

        // ── JE Creation form ───────────────────────────────────────
        me._render_je_form(d);
    },

    _render_je_form: function (d) {
        var me = this;
        var $panel = $('<div class="sinf-panel"></div>').appendTo(me.$content);
        $panel.append('<div class="sinf-panel-title">Create Offsetting Journal Entry</div>');

        // Contextual explanation
        var explanation = "";
        if (d.is_return && !d.return_against) {
            explanation = "This is a return invoice with no parent SI linked. Creating a JE will debit the receivable account to bring the outstanding to zero.";
        } else if (d.is_return && d.return_against) {
            explanation = "This is a return against <b>" + d.return_against + "</b>. Consider using Payment Reconciliation to match it against the original SI instead of a JE.";
        } else if (d.grand_total < 0) {
            explanation = "This invoice has a negative grand total, likely entered as a reversal. A JE will zero out the outstanding balance on the receivable account.";
        } else {
            explanation = "This invoice has a negative outstanding despite a positive grand total \u2014 an over-payment or credit note may have been applied. Verify before creating a JE.";
        }

        $panel.append('<div class="sinf-alert info">' + explanation + '</div>');

        // Warning if difference is non-zero
        if (Math.abs(d.difference) > 0.5) {
            $panel.append(
                '<div class="sinf-alert warn">&#9888; The GL balance and SI outstanding differ by ' +
                format_currency(d.difference) + '. Investigate the mismatch before creating a JE.</div>'
            );
        }

        var $form = $('<div class="sinf-je-form"></div>').appendTo($panel);

        // Posting date
        this.je_date_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Date", fieldname: "je_date", label: "JE Posting Date" },
            parent: $('<div></div>').appendTo($form), render_input: true,
        });
        this.je_date_ctrl.set_value(frappe.datetime.get_today());
        this.je_date_ctrl.refresh();

        // Remarks
        this.je_remarks_ctrl = frappe.ui.form.make_control({
            df: { fieldtype: "Small Text", fieldname: "je_remarks", label: "Remarks",
                  placeholder: "Reason for offsetting JE..." },
            parent: $('<div></div>').appendTo($form), render_input: true,
        });
        this.je_remarks_ctrl.set_value(
            "Offsetting JE to zero out negative outstanding on " + d.si_name + " (" + d.customer + ")"
        );
        this.je_remarks_ctrl.refresh();

        // Preview
        $panel.append(
            '<div style="background:var(--subtle-bg,#f8f9fa);border:1px solid var(--border-color);' +
            'border-radius:var(--border-radius);padding:12px 16px;margin-bottom:14px;font-size:13px;">' +
            '<b>JE Preview:</b><br>' +
            '<table class="sinf-tbl" style="margin-top:8px">' +
            '<thead><tr><th>Account</th><th class="num">Debit</th><th class="num">Credit</th></tr></thead>' +
            '<tbody>' +
            (d.outstanding < 0
                ? '<tr><td>' + d.debit_to + ' (Party: ' + d.customer + ')</td>' +
                  '<td class="num pos">' + format_currency(Math.abs(d.outstanding)) + '</td><td class="num">—</td></tr>' +
                  '<tr><td>Write Off / Suspense Account <span style="font-size:11px;color:var(--text-muted)">(from Company settings)</span></td>' +
                  '<td class="num">—</td><td class="num">' + format_currency(Math.abs(d.outstanding)) + '</td></tr>'
                : '<tr><td>' + d.debit_to + ' (Party: ' + d.customer + ')</td>' +
                  '<td class="num">—</td><td class="num neg">' + format_currency(Math.abs(d.outstanding)) + '</td></tr>' +
                  '<tr><td>Write Off / Suspense Account</td>' +
                  '<td class="num">' + format_currency(Math.abs(d.outstanding)) + '</td><td class="num">—</td></tr>'
            ) +
            '</tbody></table></div>'
        );

        this.$je_result = $('<div></div>').appendTo($panel);

        $('<button class="btn btn-danger">Create & Submit Journal Entry</button>')
            .appendTo($panel)
            .on("click", function () {
                frappe.confirm(
                    __("This will create and <b>submit</b> a Journal Entry of {0} against {1}. Proceed?",
                        [format_currency(Math.abs(d.outstanding)), d.si_name]),
                    function () { me._create_je(); }
                );
            });
    },

    _create_je: function () {
        var me = this;
        if (!me.si_data) return;

        frappe.call({
            method: SINF_BASE + "create_offset_je",
            args: {
                si_name:      me.si_data.si_name,
                posting_date: me.je_date_ctrl.get_value(),
                remarks:      me.je_remarks_ctrl.get_value(),
            },
            freeze: true, freeze_message: __("Creating Journal Entry..."),
            callback: function (r) {
                if (!r.message) return;
                me.$je_result.empty();
                if (r.message.status === "skipped") {
                    frappe.show_alert({ message: r.message.message, indicator: "blue" });
                    return;
                }
                frappe.show_alert({ message: r.message.message, indicator: "green" });
                me.$je_result.html(
                    '<div class="sinf-alert success" style="margin-top:12px">' +
                    '&#10003; Journal Entry <a href="/app/journal-entry/' +
                    encodeURIComponent(r.message.je_name) + '" target="_blank"><b>' +
                    r.message.je_name + '</b></a> created and submitted. ' +
                    'The SI outstanding has been zeroed out.' +
                    '</div>'
                );
                // Reload to reflect new state
                setTimeout(function () { me.load(); }, 1500);
            },
        });
    },

    // ── Helper renderers ──────────────────────────────────────────

    _card: function (label, value, cls) {
        return '<div class="sinf-card ' + (cls || "") + '">' +
               '<div class="lbl">' + label + '</div>' +
               '<div class="val">' + value + '</div></div>';
    },

    _panel: function ($parent, title, inner_html) {
        var $p = $('<div class="sinf-panel"></div>').appendTo($parent);
        $p.append('<div class="sinf-panel-title">' + title + '</div>');
        $p.append(inner_html);
    },

    _gl_table: function (rows) {
        if (!rows || !rows.length)
            return '<div class="sinf-empty">No GL entries found.</div>';
        var html = '<table class="sinf-tbl"><thead><tr>' +
            '<th>Account</th><th>Party</th><th class="num">Debit</th>' +
            '<th class="num">Credit</th><th class="num">Net</th><th>Remarks</th>' +
            '</tr></thead><tbody>';
        rows.forEach(function (r) {
            var net = flt(r.net, 2);
            html += '<tr>' +
                '<td>' + (r.account || "") + '</td>' +
                '<td>' + (r.party || "") + '</td>' +
                '<td class="num">' + format_currency(r.debit) + '</td>' +
                '<td class="num">' + format_currency(r.credit) + '</td>' +
                '<td class="num ' + (net < 0 ? "neg" : net > 0 ? "pos" : "") + '">' + format_currency(net) + '</td>' +
                '<td style="font-size:11px;color:var(--text-muted)">' + frappe.utils.escape_html(r.remarks || "") + '</td>' +
                '</tr>';
        });
        return html + '</tbody></table>';
    },

    _pe_table: function (rows) {
        if (!rows || !rows.length)
            return '<div class="sinf-empty">No payment entries linked.</div>';
        var html = '<table class="sinf-tbl"><thead><tr>' +
            '<th>Payment Entry</th><th>Date</th><th>Type</th>' +
            '<th class="num">Paid Amount</th><th class="num">Allocated</th><th>Remarks</th>' +
            '</tr></thead><tbody>';
        rows.forEach(function (r) {
            html += '<tr>' +
                '<td><a href="/app/payment-entry/' + encodeURIComponent(r.name) + '" target="_blank">' + r.name + '</a></td>' +
                '<td>' + r.posting_date + '</td>' +
                '<td>' + (r.payment_type || "") + '</td>' +
                '<td class="num">' + format_currency(r.paid_amount) + '</td>' +
                '<td class="num">' + format_currency(r.allocated_amount) + '</td>' +
                '<td style="font-size:11px;color:var(--text-muted)">' + frappe.utils.escape_html(r.remarks || "") + '</td>' +
                '</tr>';
        });
        return html + '</tbody></table>';
    },

    _je_table: function (rows) {
        if (!rows || !rows.length)
            return '<div class="sinf-empty">No journal entries linked.</div>';
        var html = '<table class="sinf-tbl"><thead><tr>' +
            '<th>Journal Entry</th><th>Date</th><th>Account</th>' +
            '<th class="num">Debit</th><th class="num">Credit</th><th>Remark</th>' +
            '</tr></thead><tbody>';
        rows.forEach(function (r) {
            html += '<tr>' +
                '<td><a href="/app/journal-entry/' + encodeURIComponent(r.name) + '" target="_blank">' + r.name + '</a></td>' +
                '<td>' + r.posting_date + '</td>' +
                '<td>' + (r.account || "") + '</td>' +
                '<td class="num">' + format_currency(r.debit_in_account_currency) + '</td>' +
                '<td class="num">' + format_currency(r.credit_in_account_currency) + '</td>' +
                '<td style="font-size:11px;color:var(--text-muted)">' + frappe.utils.escape_html(r.user_remark || "") + '</td>' +
                '</tr>';
        });
        return html + '</tbody></table>';
    },

    _cn_table: function (rows) {
        if (!rows || !rows.length)
            return '<div class="sinf-empty">No credit notes / returns linked.</div>';
        var html = '<table class="sinf-tbl"><thead><tr>' +
            '<th>Credit Note</th><th>Date</th>' +
            '<th class="num">Grand Total</th><th class="num">Outstanding</th>' +
            '</tr></thead><tbody>';
        rows.forEach(function (r) {
            html += '<tr>' +
                '<td><a href="/app/sales-invoice/' + encodeURIComponent(r.name) + '" target="_blank">' + r.name + '</a></td>' +
                '<td>' + r.posting_date + '</td>' +
                '<td class="num">' + format_currency(r.grand_total) + '</td>' +
                '<td class="num ' + (flt(r.outstanding_amount) < 0 ? "neg" : "") + '">' +
                format_currency(r.outstanding_amount) + '</td>' +
                '</tr>';
        });
        return html + '</tbody></table>';
    },
});

function flt(v, p) { return parseFloat((parseFloat(v) || 0).toFixed(p || 2)); }
