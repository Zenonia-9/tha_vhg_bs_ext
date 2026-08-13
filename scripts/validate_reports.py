company = env["res.company"].search([
    ("name", "=", "THUKHA SAYTANAR CO. Ltd (Victoria Hospital)"),
], limit=1)
assert company, "THUKHA SAYTANAR company was not found"
assert company.totals_below_sections, (
    "THUKHA SAYTANAR must enable Odoo's native Add totals below sections setting"
)
report_context = {"allowed_company_ids": [company.id]}
notes = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_notes").with_company(company).with_context(**report_context)
summary = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_summary").with_company(company).with_context(**report_context)

as_of_august = {
    "date": {
        "string": "As of 08/13/2026",
        "period_type": "today",
        "mode": "single",
        "date_from": "2026-04-01",
        "date_to": "2026-08-13",
        "filter": "today",
    },
    "comparison": {"filter": "previous_period", "number_period": 1},
}
for report in (notes, summary):
    comparison_options = report.get_options(as_of_august)
    comparison_period = comparison_options["comparison"]["periods"][0]
    assert comparison_period["date_to"] == "2026-07-31", (
        f"{report.name}: one previous period must end on 2026-07-31"
    )
    assert comparison_period["string"] == "As of 07/31/2026"
print("Balance Sheet prior-period month-end comparison: OK")

assert notes.name == "Management Balance Sheet Notes & Summary"
assert env.ref("tha_vhg_bs_ext.action_report_vhg_balance_sheet_notes").name == notes.name

for report in (notes, summary):
    options = report.get_options({})
    horizontal_groups = options.get("available_horizontal_groups", [])
    assert horizontal_groups, f"{report.name}: Horizontal Group is not enabled"
    horizontal_options = report.get_options({
        "selected_horizontal_group_id": horizontal_groups[0]["id"],
    })
    assert horizontal_options["selected_horizontal_group_id"] == horizontal_groups[0]["id"]
    assert horizontal_options["show_horizontal_group_total"] is False
    horizontal_lines = report._get_lines(horizontal_options)
    assert horizontal_lines, f"{report.name}: Horizontal Group did not render"
    assert all(
        len(line["columns"]) == len(horizontal_options["columns"])
        for line in horizontal_lines
    ), f"{report.name}: Horizontal Group added a redundant total column"

multi_company_ids = env["res.company"].search([], limit=3).ids
if len(multi_company_ids) > 1:
    multi_company_context = {"allowed_company_ids": multi_company_ids}
    for report_xmlid in (
        "tha_vhg_bs_ext.report_vhg_balance_sheet_notes",
        "tha_vhg_bs_ext.report_vhg_balance_sheet_summary",
    ):
        report = env.ref(report_xmlid).with_context(**multi_company_context)
        multi_company_options = report.get_options({
            "companies": [{"id": company_id} for company_id in multi_company_ids],
        })
        horizontal_options = report.get_options({
            "companies": [{"id": company_id} for company_id in multi_company_ids],
            "selected_horizontal_group_id": multi_company_options["available_horizontal_groups"][0]["id"],
        })
        assert horizontal_options["show_horizontal_group_total"] is True
        assert len(horizontal_options["columns"]) == len(multi_company_ids)
        assert len(horizontal_options["vhg_notes_header_rows"]) == 2
        assert sum(header["colspan"] for header in horizontal_options["vhg_notes_header_rows"][0]) == len(multi_company_ids)
        assert sum(header["colspan"] for header in horizontal_options["vhg_notes_header_rows"][1]) == len(multi_company_ids)
        multi_company_lines = report._get_lines(horizontal_options)
        numeric_lines = [
            line for line in multi_company_lines
            if line["columns"] and any(
                isinstance(column.get("no_format"), (int, float))
                for column in line["columns"]
            )
        ]
        assert any(
            "horizontal_group_total_data" in line for line in numeric_lines
        ), f"{report.name}: Consolidate values were not generated"
    print("Multi-company Consolidate column: OK")
    assert isinstance(options.get("vhg_notes_header_rows"), list), (
        f"{report.name}: reusable report header rows were not initialized"
    )
    lines = report._get_lines(options)
    assert lines, f"{report.name}: no lines"
    names = [line["name"] for line in lines]
    assert "ASSETS" in names
    assert "SHAREHOLDERS' EQUITY & LIABILITIES" in names
    if report == summary:
        assert "OFF BALANCE SHEET ACCOUNTS" in names
    print(f"{report.name}: {len(lines)} lines, {len(options['columns'])} columns")

notes_options = notes.get_options({"unfold_all": True})
notes_lines = notes._get_lines(notes_options)
assert any(line.get("parent_id") for line in notes_lines), "Notes: mapped accounts did not unfold"
print(f"Notes unfolded: {len(notes_lines)} lines")

folded_lines = notes._get_lines(notes.get_options({}))
folded_names = [line["name"] for line in folded_lines]
for name in ("Total ASSETS", "Total SHAREHOLDERS' EQUITY & LIABILITIES", "Total Cash at Bank"):
    assert name in folded_names, f"Missing native totals-below-section line: {name}"
assert any("|total~~" in line["id"] for line in folded_lines)
print("Notes report-local totals below sections: OK")

pnl_notes = env.ref("tha_vhg_pnl_ext.report_vhg_profit_and_loss", raise_if_not_found=False)
if pnl_notes:
    pnl_notes = pnl_notes.with_company(company).with_context(**report_context)
    pnl_lines = pnl_notes._get_lines(pnl_notes.get_options({}))
    assert any("|total~~" in line["id"] for line in pnl_lines), (
        "Odoo native totals are missing from P&L Notes"
    )
    print("P&L Notes native totals: OK")

assert notes.line_ids, "Notes must use native account.report.line records"
all_notes_lines = env["account.report.line"].search([("report_id", "=", notes.id)])
by_code = {line.code: line for line in all_notes_lines}
assert all(line.sequence for line in all_notes_lines), "Every Notes line needs an explicit sequence"
assert len(set(all_notes_lines.mapped("sequence"))) == len(all_notes_lines), (
    "Notes line sequences must be unique"
)
for line in all_notes_lines.filtered("parent_id"):
    assert line.parent_id.sequence < line.sequence, (
        f"{line.name}: parent must precede child in report editor order"
    )
for code in (
    "VHG_BS_ASSETS_SECTION", "VHG_BS_NCA_SECTION", "VHG_BS_BASE_NCA",
    "VHG_BS_OTHER_NCA_SECTION", "VHG_BS_CA_SECTION", "VHG_BS_EL_SECTION",
    "VHG_BS_EQUITY_SECTION", "VHG_BS_LIABILITY_SECTION", "VHG_BS_CL_SECTION",
    "VHG_BS_OFF_BALANCE",
):
    assert code in by_code, f"Missing native formula/group line: {code}"
for code in ("VHG_BS_PPE", "VHG_BS_CASH", "VHG_BS_TRADE_PAYABLES"):
    assert by_code[code].foldable and by_code[code].groupby == "account_id"
for code in ("VHG_BS_ASSETS_SECTION", "VHG_BS_EL_SECTION"):
    assert not by_code[code].foldable
for code in ("VHG_BS_NCA_SECTION", "VHG_BS_CA_SECTION", "VHG_BS_EQUITY_SECTION", "VHG_BS_LIABILITY_SECTION"):
    assert by_code[code].hierarchy_level == 1
assert by_code["VHG_BS_CL_SECTION"].hierarchy_level == 3
obsolete_total_codes = {
    "VHG_BS_TOTAL_OTHER_NCA", "VHG_BS_TOTAL_NCA", "VHG_BS_TOTAL_CA",
    "VHG_BS_TOTAL_EQUITY", "VHG_BS_TOTAL_CL", "VHG_BS_TOTAL_LIABILITIES",
    "VHG_BS_TOTAL_ASSETS", "VHG_BS_TOTAL_EL",
}
assert not obsolete_total_codes.intersection(by_code)
assert by_code["VHG_BS_BASE_NCA"].name == "Total Non Current Assets"

mapped_codes = {
    "VHG_BS_PPE": "210010",
    "VHG_BS_INTANGIBLE": "230015",
    "VHG_BS_INVESTMENT": "240010",
    "VHG_BS_CONSTRUCTION": "240055",
    "VHG_BS_CASH": "110110",
    "VHG_BS_BANK": "121010",
    "VHG_BS_RECEIVABLES": "130050",
    "VHG_BS_INVENTORY": "140010",
    "VHG_BS_PREPAYMENTS": "150010",
    "VHG_BS_ADVANCED_TAX": "150110",
    "VHG_BS_SHARE_CAPITAL": "400010",
    "VHG_BS_DIVIDEND": "400070",
    "RETAINED_EARNING_TOTAL": "410000",
    "VHG_BS_TRADE_PAYABLES": "310010",
    "VHG_BS_DEFERRED": "310205",
    "VHG_BS_TAX_PAYABLE": "310255",
    "VHG_BS_OTHER_PAYABLE": "310110",
}
for code, account_code in mapped_codes.items():
    formula = by_code[code].expression_ids.filtered(
        lambda expression: expression.engine == "domain"
    ).formula
    assert "account_id.code" in formula and account_code in formula, (
        f"{code} is not mapped with its supplied account codes"
    )
assert "account_id.code" in by_code["VHG_BS_OTHER_ASSETS"].expression_ids.filtered(
    lambda expression: expression.engine == "domain"
).formula

assert by_code["RET_EARN"].expression_ids.filtered(lambda expression: expression.label == "balance").formula == (
    "RETAINED_EARNING_TOTAL.balance + UNAFFECTED_EARNINGS_COPY.balance + "
    "PREV_YEAR_EARNINGS_COPY.balance"
)
assert by_code["Cur_Yr_PL"].expression_ids.filtered(lambda expression: expression.label == "balance").formula == "CURR_YEAR_EARNINGS_COPY.balance"
assert by_code["UNAFFECTED_EARNINGS_COPY"].expression_ids.filtered(lambda expression: expression.label == "balance").formula == (
    "CURR_YEAR_EARNINGS_COPY.balance + PREV_YEAR_EARNINGS_COPY.balance"
)
assert by_code["RETAINED_EARNING_TOTAL"].parent_id == by_code["RET_EARN"]
assert by_code["UNAFFECTED_EARNINGS_COPY"].parent_id == by_code["RET_EARN"]
assert by_code["PREV_YEAR_EARNINGS_COPY"].parent_id == by_code["RET_EARN"]
assert by_code["CURR_YEAR_EARNINGS_COPY"].parent_id == by_code["Cur_Yr_PL"]
current_expressions = {expression.label: expression for expression in by_code["CURR_YEAR_EARNINGS_COPY"].expression_ids}
assert current_expressions["pnl"].subformula == "cross_report(account_reports.profit_and_loss)"
assert current_expressions["pnl"].date_scope == "from_fiscalyear"
assert current_expressions["alloc"].date_scope == "from_fiscalyear"
previous_expressions = {expression.label: expression for expression in by_code["PREV_YEAR_EARNINGS_COPY"].expression_ids}
assert previous_expressions["allocated_earnings"].date_scope == "from_beginning"
assert previous_expressions["balance_domain"].date_scope == "from_beginning"
print("Retained earnings and current-year P&L source formulas: OK")

ppe_line = next(line for line in notes._get_lines(notes.get_options({})) if line["name"] == "Property, Plant and Equipment")
assert ppe_line["expand_function"] == "_report_expand_unfoldable_line_mapped_accounts_vhg_balance_sheet"
ppe_expanded = notes._expand_unfoldable_line(
    ppe_line["expand_function"], ppe_line["id"], ppe_line.get("groupby"),
    notes.get_options({}), None, 0, None,
)
ppe_account_lines = [line for line in ppe_expanded if line.get("parent_id") == ppe_line["id"]]
assert len(ppe_account_lines) == 36, "All mapped PPE accounts must be visible, including 0.00 accounts"
assert ppe_account_lines[0]["name"].startswith("210010 ")
assert ppe_account_lines[-1]["name"].startswith("220100 ")

print(f"Notes native definitions: {len(all_notes_lines)} lines")
