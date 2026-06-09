frappe.query_reports["Accounts Receivable with JV"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "party",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "ageing_based_on",
			label: __("Ageing Based On"),
			fieldtype: "Select",
			options: "Due Date\nPosting Date",
			default: "Due Date",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		// ── Section header row ─────────────────────────────────────────────
		if (data.invoice && data.invoice.startsWith("──")) {
			return `<strong style="color: var(--text-muted); font-size: 11px;">${data.invoice}</strong>`;
		}

		// ── Difference column: green = zero, red = non-zero ───────────────
		if (column.fieldname === "difference") {
			if (data.difference === null || data.difference === undefined) return value;
			const colour = Math.abs(data.difference) < 1 ? "#639922" : "#e24b4a";
			const weight = Math.abs(data.difference) >= 1 ? "600" : "400";
			return `<span style="color:${colour}; font-weight:${weight};">${value}</span>`;
		}

		// ── Status column ─────────────────────────────────────────────────
		if (column.fieldname === "status") {
			const map = {
				"Unpaid":      { color: "#e24b4a", bg: "#fdecea" },
				"Partly Paid": { color: "#ba7517", bg: "#fef3e2" },
				"Paid":        { color: "#639922", bg: "#eaf3de" },
				"Unlinked JV": { color: "#5b6dcd", bg: "#eef0fc" },
			};
			const style = map[data.status];
			if (!style) return value;
			return `<span style="
				color: ${style.color};
				background: ${style.bg};
				padding: 2px 8px;
				border-radius: 6px;
				font-size: 11px;
				font-weight: 500;
			">${data.status}</span>`;
		}

		// ── Unlinked JV column: highlight amber if non-zero ───────────────
		if (column.fieldname === "unlinked_jv_amount") {
			if (data.unlinked_jv_amount && Math.abs(data.unlinked_jv_amount) >= 1) {
				return `<span style="color:#ba7517; font-weight:500;">${value}</span>`;
			}
		}

		// ── Linked JV column: highlight blue if non-zero ──────────────────
		if (column.fieldname === "linked_jv_amount") {
			if (data.linked_jv_amount && Math.abs(data.linked_jv_amount) >= 1) {
				return `<span style="color:#5b6dcd; font-weight:500;">${value}</span>`;
			}
		}

		// ── Outstanding with JV — always bold ────────────────────────────
		if (column.fieldname === "outstanding_with_jv" && data.outstanding_with_jv !== null) {
			return `<strong>${value}</strong>`;
		}

		return value;
	},

	onload: function (report) {
		// Export button
		report.page.add_inner_button(__("Export to Excel"), function () {
			frappe.query_report.export_report("Excel");
		});

		// Info button explaining what Unlinked JV means
		report.page.add_inner_button(__("ℹ️ About Unlinked JVs"), function () {
			frappe.msgprint({
				title: __("What are Unlinked JV Adjustments?"),
				message: __(
					`<p>Journal Entries posted for cheque bounces <strong>without a Sales Invoice reference</strong>
					affect the GL balance but are invisible to the standard AR report.</p>
					<p>This report fetches all such unlinked JVs for the party and distributes them
					proportionally across open invoices so that <strong>Outstanding (with JV) = GL Balance</strong>.</p>
					<p><b>Fix:</b> When booking a bounce JV, always set:<br>
					&nbsp;&nbsp;Reference Type = <i>Sales Invoice</i><br>
					&nbsp;&nbsp;Reference Name = the bounced invoice<br>
					This will make the "Linked JV Adj." column populate instead, giving invoice-level accuracy.</p>`
				),
				indicator: "blue",
			});
		});
	},
};
