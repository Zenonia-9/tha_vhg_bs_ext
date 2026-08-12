company = env["res.company"].search([
    ("name", "=", "THUKHA SAYTANAR CO. Ltd (Victoria Hospital)"),
], limit=1)
assert company, "THUKHA SAYTANAR company was not found"
report_context = {"allowed_company_ids": [company.id]}
notes = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_notes").with_company(company).with_context(**report_context)
summary = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_summary").with_company(company).with_context(**report_context)

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
    assert report._get_lines(horizontal_options), f"{report.name}: Horizontal Group did not render"
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
if pnl_notes and not company.totals_below_sections:
    pnl_notes = pnl_notes.with_company(company).with_context(**report_context)
    pnl_lines = pnl_notes._get_lines(pnl_notes.get_options({}))
    assert not any("|total~~" in line["id"] for line in pnl_lines), (
        "Balance Sheet totals leaked into P&L Notes"
    )
    print("P&L Notes isolation: OK")

assert notes.line_ids, "Notes must use native account.report.line records"
all_notes_lines = env["account.report.line"].search([("report_id", "=", notes.id)])
by_code = {line.code: line for line in all_notes_lines}
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
    "VHG_BS_RETAINED": "410000",
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

handler = env["tha.vhg.balance.sheet.summary.report.handler"]
assert not handler._matches(
    {"code": "999999", "name": "Building & infrastructure development - gross"},
    {"codes": ("210010",)},
), "Balance Sheet fallback matching must never use an account name"
print(f"Notes native definitions: {len(all_notes_lines)} lines")
