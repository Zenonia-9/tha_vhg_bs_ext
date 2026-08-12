notes = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_notes")
summary = env.ref("tha_vhg_bs_ext.report_vhg_balance_sheet_summary")

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

if env.company.totals_below_sections:
    folded_lines = notes._get_lines(notes.get_options({}))
    folded_names = [line["name"] for line in folded_lines]
    for name in ("Total ASSETS", "Total SHAREHOLDERS' EQUITY & LIABILITIES", "Total Cash at Bank"):
        assert name in folded_names, f"Missing native totals-below-section line: {name}"
    assert any("|total~~" in line["id"] for line in folded_lines)
    print("Notes native totals below sections: OK")

assert notes.line_ids, "Notes must use native account.report.line records"
all_notes_lines = env["account.report.line"].search([("report_id", "=", notes.id)])
by_code = {line.code: line for line in all_notes_lines}
for code in ("VHG_BS_ASSETS_SECTION", "VHG_BS_TOTAL_EQUITY", "VHG_BS_EL_SECTION", "VHG_BS_OFF_BALANCE"):
    assert code in by_code, f"Missing native total line: {code}"
for code in ("VHG_BS_PPE", "VHG_BS_CASH", "VHG_BS_TRADE_PAYABLES"):
    assert by_code[code].foldable and by_code[code].groupby == "account_id"
for code in ("VHG_BS_ASSETS_SECTION", "VHG_BS_EL_SECTION"):
    assert not by_code[code].foldable
for code in ("VHG_BS_NCA_SECTION", "VHG_BS_CA_SECTION", "VHG_BS_EQUITY_SECTION", "VHG_BS_LIABILITY_SECTION", "VHG_BS_CL_SECTION"):
    assert by_code[code].hierarchy_level == 1
assert "VHG_BS_TOTAL_ASSETS" not in by_code
assert "VHG_BS_TOTAL_EL" not in by_code
print(f"Notes native definitions: {len(all_notes_lines)} lines")
