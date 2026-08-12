# -*- coding: utf-8 -*-
"""Management Balance Sheet reports based on the VHG source definitions."""

from collections import defaultdict

from odoo import models
from odoo.tools import SQL


def _row(key, name, *, codes=(), account_names=(), children=(), level=1, total=False, unfold=True):
    return {
        "key": key, "name": name, "codes": tuple(codes), "children": tuple(children),
        "account_names": tuple(account_names),
        "level": level, "total": total, "unfold": unfold,
    }


PPE_CODES = tuple(
    f"{prefix}{suffix:03d}"
    for prefix in (210, 220)
    for suffix in (10, 15, 20, 25, 30, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)
)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def tha_vhg_attach_balance_sheet_management_menu(self):
        """Use the existing shared menu without making another addon a dependency."""
        own_root = self.env.ref("tha_vhg_bs_ext.menu_vhg_management_reports")
        existing_root = self.search([
            ("id", "!=", own_root.id),
            ("name", "=", "Management Reports"),
            ("parent_id", "=", self.env.ref("account.menu_finance_configuration").id),
        ], order="id", limit=1)
        target_root = existing_root or own_root
        self.env.ref("tha_vhg_bs_ext.menu_action_report_vhg_balance_sheet_notes").parent_id = target_root
        self.env.ref("tha_vhg_bs_ext.menu_action_report_vhg_balance_sheet_summary").parent_id = target_root


class VhgBalanceSheetReportBase(models.AbstractModel):
    _name = "tha.vhg.balance.sheet.report.base"
    _inherit = "account.report.custom.handler"
    _description = "VHG Balance Sheet Report Base"

    _REPORT_TITLE = ""
    _ROWS = ()

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        companies = self.env["res.company"].browse(report.get_report_company_ids(options))
        options.update({
            "vhg_notes_company_names": ", ".join(companies.mapped("name")) or self.env.company.name,
            "vhg_notes_report_title": self._REPORT_TITLE,
            # NotesReportHeader iterates this value directly. Keep the native
            # account-report period headers while guaranteeing an iterable
            # value when the report has no comparison columns.
            "vhg_notes_header_rows": options.get("column_headers", []),
        })
        options["custom_display_config"].update({
            "templates": {"AccountReportHeader": "tha_vhg_bs_ext.BalanceSheetReportHeader"},
            "css_custom_class": "o_vhg_balance_sheet",
        })

    @staticmethod
    def _matches(account, row):
        code = account["code"]
        code_matches = bool(code) and any(
            code == spec if isinstance(spec, str)
            else spec[0] <= code <= spec[1]
            for spec in row["codes"]
        )
        return code_matches or account["name"] in row["account_names"]

    def _query_accounts(self, report, options):
        result = {}
        companies = report.get_report_company_ids(options)
        accounts = self.env["account.account"].search([
            ("company_ids", "in", companies),
        ])
        for group_key, column_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_options, "from_beginning")
            self.env.cr.execute(SQL(
                """
                    SELECT account_move_line.account_id,
                           COALESCE(SUM(%(balance)s), 0.0) AS balance
                      FROM %(from_clause)s
                      %(currency_join)s
                     WHERE %(where_clause)s
                  GROUP BY account_move_line.account_id
                """,
                balance=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                from_clause=query.from_clause,
                currency_join=report._currency_table_aml_join(column_options),
                where_clause=query.where_clause,
            ))
            balances = {item["account_id"]: item["balance"] for item in self.env.cr.dictfetchall()}
            result[group_key] = {
                account.id: {
                    "id": account.id,
                    "code": (account.code or "").strip(),
                    "name": account.name or "",
                    "balance": balances.get(account.id, 0.0),
                }
                for account in accounts
            }
        return result

    def _values(self, account_data):
        values = defaultdict(dict)
        rows = {row["key"]: row for row in self._ROWS}
        for row in self._ROWS:
            for group_key, accounts in account_data.items():
                values[row["key"]][group_key] = sum(
                    account["balance"] for account in accounts.values()
                    if self._matches(account, row)
                )

        def aggregate(key, group_key):
            row = rows[key]
            if row["children"]:
                values[key][group_key] = sum(
                    aggregate(child, group_key) for child in row["children"]
                )
            return values[key][group_key]

        for row in self._ROWS:
            for group_key in account_data:
                aggregate(row["key"], group_key)
        return values, rows

    def _columns(self, report, options, balances):
        return [report._build_column_dict(
            balances.get(column["column_group_key"], 0.0), column, options=options,
        ) for column in options["columns"]]

    def _line(self, report, options, row, balances):
        line_id = report._get_generic_line_id(None, None, markup=f"vhg_bs_{row['key']}")
        return {
            "id": line_id,
            "name": row["name"],
            "level": row["level"],
            "class": "fw-bold" if row["total"] else "",
            "columns": self._columns(report, options, balances),
            "unfoldable": bool(row["codes"] and row["unfold"]),
            "unfolded": line_id in options.get("unfolded_lines", []) or options.get("unfold_all", False),
            "expand_function": "_report_expand_unfoldable_line_vhg_balance_sheet",
        }

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        account_data = self._query_accounts(report, options)
        values, _rows = self._values(account_data)
        return [(0, self._line(report, options, row, values[row["key"]])) for row in self._ROWS]

    def _report_expand_unfoldable_line_vhg_balance_sheet(
        self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None,
    ):
        report = self.env["account.report"].browse(options["report_id"])
        markup, model, _record_id = report._parse_line_id(line_dict_id)[-1]
        key = markup.removeprefix("vhg_bs_") if not model else ""
        row = next((item for item in self._ROWS if item["key"] == key), None)
        if not row:
            return {"lines": [], "offset_increment": 0, "has_more": False}
        account_data = self._query_accounts(report, options)
        account_ids = sorted({
            account_id for accounts in account_data.values() for account_id, account in accounts.items()
            if self._matches(account, row)
        }, key=lambda account_id: next(iter(account_data.values()))[account_id]["code"])
        lines = []
        for account_id in account_ids:
            sample = next(iter(account_data.values()))[account_id]
            balances = {key: accounts[account_id]["balance"] for key, accounts in account_data.items()}
            lines.append({
                "id": report._get_generic_line_id("account.account", account_id, parent_line_id=line_dict_id),
                "parent_id": line_dict_id,
                "name": f"{sample['code']} {sample['name']}",
                "level": row["level"] + 1,
                "columns": self._columns(report, options, balances),
                "caret_options": "account.account",
            })
        return {"lines": lines, "offset_increment": len(lines), "has_more": False}


ASSET_DETAIL = (
    _row("ppe", "Property, Plant and Equipment", codes=PPE_CODES, account_names=("Building & infrastructure development - gross",), level=2),
    _row("intangibles", "Intangible Assets", codes=("230010", "230015", "230020"), account_names=("Intangible Assets",), level=2),
    _row("investment_associates", "Investment in Associates", codes=(("240010", "240050"),), account_names=("Investment in (Innovative Diagnostics)-Subsidiary 80%",), level=3),
    _row("construction", "Construction", codes=("140120", ("240055", "240085"), "140210"), account_names=("VTR Extension-Construction-Material",), level=3),
    _row("cash", "Cash & Cash Equivalents", codes=("110110", "110111", "110112", "110120", "110130", "110140", "110190"), account_names=("Cash in hand - KS (Front Office)",), level=2),
    _row("bank", "Cash at Bank", codes=(("121010", "128050"), "131011"), account_names=("A Bank -Trust Call Saving -MMK (0021011200019184)",), level=2),
    _row("recv_external_personal", "Receivable-External-Personal", codes=(("130010", "130099"),), account_names=("Trade Receivable - Inpatient/Outpatient Receivable",), level=3),
    _row("recv_external_corporate", "Receivable-External-Corporate", codes=(("130100", "130199"),), level=3),
    _row("recv_external_rental", "Receivable-External-Rental", codes=(("130200", "130299"),), level=3),
    _row("recv_external_complex", "Receivable-External-Complex", codes=(("130300", "130399"),), level=3),
    _row("recv_internal", "Receivable-Internal", codes=(("130400", "130499"),), level=3),
    _row("recv_internal_vtr", "Receivable-Internal company (within VTR)", codes=(("130500", "130599"),), level=3),
    _row("recv_internal_other", "Receivable-Internal company (out of VTR)", codes=(("130600", "130699"),), level=3),
    _row("recv_boi", "Receivable-BOI,BOD", codes=(("130700", "130799"),), level=3),
    _row("recv_other", "Receivable-Other", codes=(("130800", "130999"),), account_names=("Other Receivable - Others",), level=3),
    _row("recv_inpatient", "Inpatient Receivable", codes=(("131000", "131999"),), level=3),
    _row("inventory", "Inventory", codes=(("140010", "140200"),), account_names=("Pharmacy",), level=2),
    _row("prepayments", "Prepaid and Advance Payments", codes=(("150010", "150150"),), account_names=("Prepaid Expenses",), level=2),
    _row("advanced_tax", "Advanced Tax", codes=(("160000", "169999"),), account_names=("Advance Income Tax",), level=2),
    _row("other_assets", "Others", codes=(("170000", "199999"),), account_names=("Deposit payment",), level=2),
)

EQUITY_LIABILITY_DETAIL = (
    _row("share_capital", "Issued & Paid Up Share Capital", codes=("400010", "400020", "400030"), account_names=("Ordinary Share",), level=2),
    _row("dividend", "Dividend", codes=("400070",), account_names=("Dividend Payable",), level=2),
    _row("retained", "410000 Retained Earning", codes=("410000",), account_names=("Retained Earnings",), level=3),
    _row("unallocated", "Unallocated Earnings", codes=(("410020", "410099"),), level=3),
    _row("previous_unallocated", "Previous Years Unallocated Earnings", codes=(("410100", "419999"),), level=3),
    _row("current_profit", "410010 Current year's profit or loss", codes=("410010",), account_names=("Current year's profit or loss",), level=3),
    _row("noncurrent_liabilities", "NON CURRENT LIABILITIES", codes=("320010", "320015"), account_names=("Long Term Loans",), level=2),
    _row("trade_payables", "Trade & Other Payables", codes=(("310020", "310060"), ("320020", "320035")), account_names=("Trade payables - Supplier",), level=3),
    _row("deferred_income", "Advance Receipt & Deferred Income", codes=(("310200", "310230"),), account_names=("Deferred Income",), level=3),
    _row("tax_payable", "Current Tax Payable", codes=(("310250", "310280"),), account_names=("Income Tax Payable",), level=3),
    _row("other_payable", "Other Current Payable", codes=(("310090", "310140"),), account_names=("Payable Expense",), level=3),
    _row("off_balance", "OFF BALANCE SHEET ACCOUNTS", codes=(("900000", "999999"),), level=0, total=True),
)


class VhgBalanceSheetNotesReportHandler(VhgBalanceSheetReportBase):
    _name = "tha.vhg.balance.sheet.notes.report.handler"
    _description = "VHG Balance Sheet Notes Report Handler"
    _REPORT_TITLE = "Management Balance Sheet Notes & Summary"

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None,
    ):
        """The Notes report is defined by native account.report.line records."""
        return []

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        # Native groupby expressions create a synthetic "Total ..." row even
        # while folded. The VHG statement displays only the named statement
        # line and its accounts when deliberately unfolded.
        lines = [line for line in lines if "|total~~" not in line["id"]]
        bold_codes = {
            "VHG_BS_ASSETS_SECTION", "VHG_BS_NCA_SECTION", "VHG_BS_OTHER_NCA_SECTION",
            "VHG_BS_TOTAL_OTHER_NCA", "VHG_BS_TOTAL_NCA", "VHG_BS_CA_SECTION",
            "VHG_BS_TOTAL_CA", "VHG_BS_TOTAL_ASSETS", "VHG_BS_EL_SECTION",
            "VHG_BS_EQUITY_SECTION", "VHG_BS_TOTAL_EQUITY", "VHG_BS_LIABILITY_SECTION",
            "VHG_BS_CL_SECTION", "VHG_BS_TOTAL_CL", "VHG_BS_TOTAL_LIABILITIES",
            "VHG_BS_TOTAL_EL",
        }
        section_codes = {"VHG_BS_ASSETS_SECTION", "VHG_BS_EL_SECTION"}
        report_lines = self.env["account.report.line"].search([("report_id", "=", report.id)])
        code_by_id = {line.id: line.code for line in report_lines}
        for line in lines:
            _model, record_id = report._get_model_info_from_id(line["id"])
            code = code_by_id.get(record_id)
            if code in bold_codes:
                line["class"] = f"{line.get('class', '')} fw-bold".strip()
            if code in section_codes:
                line["class"] = f"{line.get('class', '')} o_vhg_bs_section".strip()
        return lines

    _ROWS = (
        _row("assets", "ASSETS", children=("noncurrent_assets", "current_assets"), level=0, total=True),
        _row("noncurrent_assets", "Non Current Assets", children=("ppe", "intangibles", "other_noncurrent"), level=1, total=True),
        ASSET_DETAIL[0], ASSET_DETAIL[1],
        _row("total_noncurrent", "Total Non Current Assets", children=("ppe", "intangibles"), level=2, total=True),
        _row("other_noncurrent", "Other Non Current Assets", children=("investment_associates", "construction"), level=2, total=True),
        ASSET_DETAIL[2], ASSET_DETAIL[3],
        _row("current_assets", "Current Assets", children=("cash", "bank", "receivables", "inventory", "prepayments", "advanced_tax", "other_assets"), level=1, total=True),
        ASSET_DETAIL[4], ASSET_DETAIL[5],
        _row("receivables", "Trade & Other Receivables", children=tuple(row["key"] for row in ASSET_DETAIL[6:16]), level=2, total=True),
        *ASSET_DETAIL[6:],
        _row("equity_liabilities", "SHAREHOLDERS' EQUITY & LIABILITIES", children=("equity", "liabilities"), level=0, total=True),
        _row("equity", "SHAREHOLDERS' EQUITY", children=("share_capital", "dividend", "retained_earnings", "current_year_profit"), level=1, total=True),
        EQUITY_LIABILITY_DETAIL[0], EQUITY_LIABILITY_DETAIL[1],
        _row("retained_earnings", "Retained Earning", children=("retained", "unallocated", "previous_unallocated"), level=2, total=True),
        *EQUITY_LIABILITY_DETAIL[2:5],
        _row("current_year_profit", "Current year's profit or loss", children=("current_profit",), level=2, total=True),
        EQUITY_LIABILITY_DETAIL[5],
        _row("liabilities", "LIABILITIES", children=("noncurrent_liabilities", "current_liabilities"), level=1, total=True),
        *EQUITY_LIABILITY_DETAIL[6:7],
        _row("current_liabilities", "CURRENT LIABILITIES", children=("trade_payables", "deferred_income", "tax_payable", "other_payable"), level=2, total=True),
        *EQUITY_LIABILITY_DETAIL[7:],
    )


class VhgBalanceSheetSummaryReportHandler(VhgBalanceSheetReportBase):
    _name = "tha.vhg.balance.sheet.summary.report.handler"
    _description = "VHG Balance Sheet Summary Report Handler"
    _REPORT_TITLE = "Management Balance Sheet Summary"
    _ROWS = (
        _row("assets", "ASSETS", children=("total_noncurrent_summary", "current_assets"), level=0, total=True),
        _row("total_noncurrent_summary", "Total Non Current Assets", children=("noncurrent_summary", "other_noncurrent"), level=1, total=True),
        _row("noncurrent_summary", "Non Current Assets", children=("ppe", "intangibles"), level=2, total=True),
        ASSET_DETAIL[0], ASSET_DETAIL[1],
        _row("other_noncurrent", "Other Non Current Assets", children=("investment_associates", "construction"), level=2, total=True),
        ASSET_DETAIL[2], ASSET_DETAIL[3],
        _row("current_assets", "Current Assets", children=("cash", "bank", "receivables_summary", "inventory", "prepayments", "advanced_tax", "other_assets"), level=1, total=True),
        ASSET_DETAIL[4], ASSET_DETAIL[5],
        _row("receivables_summary", "Trade & Other Receivables", codes=(("130010", "131999"),), account_names=("Trade Receivable - Inpatient/Outpatient Receivable",), level=2),
        *ASSET_DETAIL[16:],
        _row("equity_liabilities", "SHAREHOLDERS' EQUITY & LIABILITIES", children=("equity_summary", "liabilities_summary"), level=0, total=True),
        _row("equity_summary", "SHAREHOLDERS' EQUITY", children=("share_capital", "advance_share", "retained_summary", "unallocated", "current_profit", "previous_unallocated", "joint_investment"), level=1, total=True),
        EQUITY_LIABILITY_DETAIL[0],
        _row("advance_share", "Advance Share Capital", codes=("400040",), account_names=("Advance Capital",), level=2),
        _row("retained_summary", "Retained Earning", codes=("410000",), account_names=("Retained Earnings",), level=2),
        EQUITY_LIABILITY_DETAIL[3], EQUITY_LIABILITY_DETAIL[5], EQUITY_LIABILITY_DETAIL[4],
        _row("joint_investment", "Joint Investment for Departments", codes=("320020",), level=2),
        _row("liabilities_summary", "LIABILITIES", children=("noncurrent_liabilities", "trade_payables", "deferred_income", "tax_payable", "other_payable"), level=1, total=True),
        *EQUITY_LIABILITY_DETAIL[6:],
    )
