import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def validate_filters(filters):
    if not filters.from_date or not filters.to_date:
        frappe.throw(_("From Date and To Date are required."))
    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date cannot be after To Date."))
    if not filters.company:
        frappe.throw(_("Company is required."))
    if not filters.fiscal_year:
        frappe.throw(_("Fiscal Year is required."))


def get_columns():
    return [
        {
            "label": _("Sales Person Target"),
            "fieldname": "target_doc",
            "fieldtype": "Link",
            "options": "Sales Person Target",
            "width": 180,
        },
        {
            "label": _("Group / Owner"),
            "fieldname": "group_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 160,
        },
        {
            "label": _("Sales Person"),
            "fieldname": "sales_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 160,
        },
        {
            "label": _("Item Group"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 140,
        },
        {
            "label": _("Target Qty"),
            "fieldname": "target_qty",
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "label": _("Target Amount"),
            "fieldname": "target_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Achieved Qty"),
            "fieldname": "achieved_qty",
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "label": _("Achieved Amount"),
            "fieldname": "achieved_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("Variance"),
            "fieldname": "variance",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Achievement %"),
            "fieldname": "achievement_pct",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Data",
            "hidden": 1,
            "width": 80,
        },
    ]


def get_data(filters):
    # ----------------------------------------------------------------
    # Step 1: Pull all target rows from submitted Sales Person Targets
    #         that match the filter criteria.
    # ----------------------------------------------------------------
    target_conditions = [
        "spt.docstatus = 1",
        "spt.company = %(company)s",
        "spt.fiscal_year = %(fiscal_year)s",
        "spt.period_start_date <= %(to_date)s",
        "spt.period_end_date >= %(from_date)s",
    ]
    target_values = {
        "company": filters.company,
        "fiscal_year": filters.fiscal_year,
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("sales_person"):
        target_conditions.append(
            "(spt.sales_person = %(sales_person)s OR sptd.sales_person = %(sales_person)s)"
        )
        target_values["sales_person"] = filters.sales_person

    if filters.get("item_group"):
        target_conditions.append(
            "(sptd.item_group = %(item_group)s OR sptd.item_group IS NULL OR sptd.item_group = '')"
        )
        target_values["item_group"] = filters.item_group

    condition_sql = " AND ".join(target_conditions)

    target_rows = frappe.db.sql(
        """
        SELECT
            spt.name            AS target_doc,
            spt.sales_person    AS group_person,
            spt.is_group        AS is_group,
            spt.company         AS company,
            sptd.name           AS detail_name,
            sptd.sales_person   AS sales_person,
            sptd.item_group     AS item_group,
            sptd.target_amount  AS target_amount,
            sptd.target_qty     AS target_qty
        FROM `tabSales Person Target` spt
        INNER JOIN `tabSales Person Target Detail` sptd
            ON sptd.parent = spt.name
        WHERE {condition_sql}
        ORDER BY spt.name, sptd.idx
        """.format(condition_sql=condition_sql),
        values=target_values,
        as_dict=True,
    )

    if not target_rows:
        return []

    # ----------------------------------------------------------------
    # Step 2: For each unique (sales_person, item_group) combo in the
    #         target rows, query Delivery Notes to get actual achievement.
    #
    #         Achievement is measured from submitted Delivery Notes
    #         (docstatus=1) within the report date range, joined to
    #         Sales Team on the linked Sales Invoice, or directly from
    #         the DN Sales Team child table if available.
    #
    #         Priority lookup order:
    #           1. Sales Team child table on Delivery Note itself
    #              (dn.sales_team -> Sales Person)
    #           2. Fall back to the Sales Order / Sales Invoice linked
    #              to the DN and look up Sales Team there.
    #
    #         Item Group is matched from Delivery Note Item -> item_group
    #         (which is stored directly on the DN item row in ERPNext).
    # ----------------------------------------------------------------

    # Get company currency once
    company_currency = frappe.db.get_value("Company", filters.company, "default_currency") or "INR"

    # Build a unique key set of (effective_sales_person, item_group) to
    # fetch achievement data for all combinations in one query.
    # effective_sales_person: use sptd.sales_person if set, else spt.sales_person
    combos = {}
    for row in target_rows:
        sp = row.sales_person or row.group_person
        ig = row.item_group or None
        key = (sp, ig)
        if key not in combos:
            combos[key] = {"achieved_amount": 0.0, "achieved_qty": 0.0}

    # Fetch achievement per (sales_person, item_group) from Delivery Notes
    _fill_dn_achievements(combos, filters)

    # ----------------------------------------------------------------
    # Step 3: Build the final data rows
    # ----------------------------------------------------------------
    data = []
    for row in target_rows:
        sp = row.sales_person or row.group_person
        ig = row.item_group or None
        key = (sp, ig)

        achieved_amount = flt(combos.get(key, {}).get("achieved_amount", 0))
        achieved_qty    = flt(combos.get(key, {}).get("achieved_qty", 0))
        target_amount   = flt(row.target_amount)
        target_qty      = flt(row.target_qty)
        variance        = achieved_amount - target_amount

        if target_amount > 0:
            achievement_pct = round((achieved_amount / target_amount) * 100, 2)
        else:
            achievement_pct = 0.0

        if not filters.get("show_zero_target") and target_amount == 0 and target_qty == 0:
            continue

        if filters.get("item_group") and ig and ig != filters.item_group:
            continue

        data.append({
            "target_doc":      row.target_doc,
            "group_person":    row.group_person,
            "sales_person":    row.sales_person or "",
            "item_group":      row.item_group or "",
            "target_qty":      target_qty,
            "target_amount":   target_amount,
            "achieved_qty":    achieved_qty,
            "achieved_amount": achieved_amount,
            "variance":        variance,
            "achievement_pct": achievement_pct,
            "currency":        company_currency,
        })

    # ----------------------------------------------------------------
    # Step 4: Append a summary / grand total row
    # ----------------------------------------------------------------
    if data:
        total_target   = sum(r["target_amount"] for r in data)
        total_achieved = sum(r["achieved_amount"] for r in data)
        total_tgt_qty  = sum(r["target_qty"] for r in data)
        total_ach_qty  = sum(r["achieved_qty"] for r in data)
        total_variance = total_achieved - total_target
        total_pct      = round((total_achieved / total_target) * 100, 2) if total_target else 0.0

        data.append({
            "target_doc":      "",
            "group_person":    "",
            "sales_person":    "TOTAL",
            "item_group":      "",
            "target_qty":      total_tgt_qty,
            "target_amount":   total_target,
            "achieved_qty":    total_ach_qty,
            "achieved_amount": total_achieved,
            "variance":        total_variance,
            "achievement_pct": total_pct,
            "currency":        company_currency,
            "bold":            1,
        })

    return data


def _fill_dn_achievements(combos, filters):
    """
    For every (sales_person, item_group) combo in `combos`, sum up
    base_net_amount and qty from submitted Delivery Note Items where:
      - The DN's posting_date is within filters.from_date .. to_date
      - The DN's company matches
      - The DN is linked to a Sales Team entry for the sales person
        (checked on the DN directly via dn_detail.against_sales_team,
         or via the Sales Team child table on the Delivery Note)

    ERPNext stores Sales Team on Delivery Note in the `sales_team`
    child table (same as Sales Invoice).  If empty, it falls back
    to the linked Sales Order's sales_team.

    item_group is taken from Delivery Note Item -> item_group field.
    When the target row has no item_group (None), ALL items for that
    sales person are summed regardless of item group.
    """
    if not combos:
        return

    # Collect all unique sales persons we need data for
    unique_sps = list(set(sp for (sp, ig) in combos.keys() if sp))
    if not unique_sps:
        return

    # Build IN clause placeholders
    sp_placeholders = ", ".join(["%s"] * len(unique_sps))

    # Main query: join DN -> DN Item -> Sales Team on DN
    # We use a LEFT JOIN on the DN's own sales_team child table.
    # If the DN has no sales_team rows, we try the linked Sales Order.
    query = """
        SELECT
            st.sales_person         AS sales_person,
            dni.item_group          AS item_group,
            SUM(dni.base_net_amount) AS achieved_amount,
            SUM(dni.qty)            AS achieved_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent
        INNER JOIN `tabSales Team` st
            ON st.parent = dn.name
            AND st.parenttype = 'Delivery Note'
            AND st.sales_person IN ({sp_placeholders})
        WHERE
            dn.docstatus = 1
            AND dn.company = %s
            AND dn.posting_date BETWEEN %s AND %s
        GROUP BY st.sales_person, dni.item_group
    """.format(sp_placeholders=sp_placeholders)

    values = unique_sps + [filters.company, filters.from_date, filters.to_date]
    rows = frappe.db.sql(query, values=values, as_dict=True)

    # If DN has no Sales Team rows, fall back to linked Sales Order's team
    # by checking which DNs had zero ST coverage and re-querying via SO
    dn_with_st = frappe.db.sql(
        """
        SELECT DISTINCT parent FROM `tabSales Team`
        WHERE parenttype = 'Delivery Note'
        AND sales_person IN ({sp_placeholders})
        """.format(sp_placeholders=sp_placeholders),
        values=unique_sps,
        as_list=True,
    )
    dn_with_st_set = {r[0] for r in dn_with_st}

    # Fallback: for DNs without their own Sales Team, use the Sales Order
    fallback_rows = frappe.db.sql(
        """
        SELECT
            st.sales_person          AS sales_person,
            dni.item_group           AS item_group,
            SUM(dni.base_net_amount) AS achieved_amount,
            SUM(dni.qty)             AS achieved_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent
        INNER JOIN `tabSales Team` st
            ON st.parent = dni.against_sales_order
            AND st.parenttype = 'Sales Order'
            AND st.sales_person IN ({sp_placeholders})
        WHERE
            dn.docstatus = 1
            AND dn.company = %s
            AND dn.posting_date BETWEEN %s AND %s
            AND dn.name NOT IN (
                SELECT DISTINCT parent FROM `tabSales Team`
                WHERE parenttype = 'Delivery Note'
            )
        GROUP BY st.sales_person, dni.item_group
        """.format(sp_placeholders=sp_placeholders),
        values=unique_sps + [filters.company, filters.from_date, filters.to_date],
        as_dict=True,
    )

    all_rows = list(rows) + list(fallback_rows)

    # Aggregate into combos dict
    # Key (sp, ig) where ig=None means "all item groups for this sp"
    for r in all_rows:
        sp = r.sales_person
        ig = r.item_group or None

        # Match to exact (sp, ig) combo
        key_exact = (sp, ig)
        if key_exact in combos:
            combos[key_exact]["achieved_amount"] += flt(r.achieved_amount)
            combos[key_exact]["achieved_qty"]    += flt(r.achieved_qty)

        # Also roll up into (sp, None) combos which mean "all items"
        key_any_ig = (sp, None)
        if key_any_ig in combos and ig is not None:
            combos[key_any_ig]["achieved_amount"] += flt(r.achieved_amount)
            combos[key_any_ig]["achieved_qty"]    += flt(r.achieved_qty)