# -*- coding: utf-8 -*-
"""Standalone handlers for the VHG management Balance Sheet reports."""

import ast

from odoo import models
from odoo.tools import SQL


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def tha_vhg_attach_balance_sheet_management_menu(self):
        """Attach to an installed shared root without depending on its addon."""
        own_root = self.env.ref("tha_vhg_bs_ext.menu_vhg_management_reports")
        shared_root = self.search([
            ("id", "!=", own_root.id),
            ("name", "=", "Management Reports"),
            ("parent_id", "=", self.env.ref("account.menu_finance_configuration").id),
        ], order="id", limit=1)
        target_root = shared_root or own_root
        self.env.ref("tha_vhg_bs_ext.menu_action_report_vhg_balance_sheet_notes").parent_id = target_root
        self.env.ref("tha_vhg_bs_ext.menu_action_report_vhg_balance_sheet_summary").parent_id = target_root


class VhgBalanceSheetReportBase(models.AbstractModel):
    _name = "tha.vhg.balance.sheet.report.base"
    _inherit = "account.report.custom.handler"
    _description = "VHG Balance Sheet Report Base"

    _REPORT_TITLE = ""

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options,
        )
        companies = self.env["res.company"].browse(
            report.get_report_company_ids(options)
        )
        options.update({
            "vhg_notes_company_names": (
                ", ".join(companies.mapped("name")) or self.env.company.name
            ),
            "vhg_notes_report_title": self._REPORT_TITLE,
            "vhg_notes_header_rows": options.get("column_headers", []),
        })
        options["custom_display_config"].update({
            "templates": {
                "AccountReportHeader": "tha_vhg_bs_ext.BalanceSheetReportHeader",
            },
            "css_custom_class": "o_vhg_balance_sheet",
        })


class VhgBalanceSheetNotesReportHandler(VhgBalanceSheetReportBase):
    _name = "tha.vhg.balance.sheet.notes.report.handler"
    _description = "VHG Balance Sheet Notes Report Handler"
    _REPORT_TITLE = "Management Balance Sheet Notes & Summary"

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None,
    ):
        """Notes is defined entirely by native account.report.line records."""
        return []

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        bold_codes = {
            "VHG_BS_ASSETS_SECTION", "VHG_BS_NCA_SECTION", "VHG_BS_BASE_NCA",
            "VHG_BS_OTHER_NCA_SECTION", "VHG_BS_CA_SECTION", "VHG_BS_EL_SECTION",
            "VHG_BS_EQUITY_SECTION", "VHG_BS_LIABILITY_SECTION", "VHG_BS_CL_SECTION",
        }
        section_codes = {"VHG_BS_ASSETS_SECTION", "VHG_BS_EL_SECTION"}
        report_lines = self.env["account.report.line"].search([
            ("report_id", "=", report.id),
        ])
        code_by_id = {line.id: line.code for line in report_lines}
        for line in lines:
            _model, record_id = report._get_model_info_from_id(line["id"])
            code = code_by_id.get(record_id)
            if code in bold_codes:
                line["class"] = f"{line.get('class', '')} fw-bold".strip()
            if code in section_codes:
                line["class"] = f"{line.get('class', '')} o_vhg_bs_section".strip()
            if code and self._mapped_account_codes(report_lines.browse(record_id)):
                line["expand_function"] = (
                    "_report_expand_unfoldable_line_mapped_accounts_vhg_balance_sheet"
                )
        return lines

    @staticmethod
    def _mapped_account_codes(report_line):
        expression = report_line.expression_ids.filtered(
            lambda item: item.engine == "domain" and "account_id.code" in item.formula
        )[:1]
        if not expression:
            return []
        try:
            domain = ast.literal_eval(expression.formula)
        except (SyntaxError, ValueError):
            return []
        return next((
            value for field_name, operator, value in domain
            if field_name == "account_id.code" and operator == "in"
        ), [])

    def _report_expand_unfoldable_line_mapped_accounts_vhg_balance_sheet(
        self, line_dict_id, groupby, options, progress, offset,
        unfold_all_batch_data=None,
    ):
        report = self.env["account.report"].browse(options["report_id"])
        report_line_id = next((
            record_id
            for _markup, model, record_id in reversed(report._parse_line_id(line_dict_id))
            if model == "account.report.line"
        ), None)
        report_line = self.env["account.report.line"].browse(report_line_id)
        account_codes = self._mapped_account_codes(report_line)
        if not account_codes:
            return {"lines": [], "offset_increment": 0, "has_more": False}

        accounts = self.env["account.account"].search([
            ("company_ids", "in", report.get_report_company_ids(options)),
            ("code", "in", account_codes),
        ])
        accounts_by_code = {account.code: account for account in accounts}
        ordered_accounts = [
            accounts_by_code[code] for code in account_codes if code in accounts_by_code
        ]
        balances_by_group = {}
        for group_key, column_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_options, "from_beginning")
            self.env.cr.execute(SQL(
                """
                    SELECT account_move_line.account_id,
                           COALESCE(SUM(%(balance)s), 0.0) AS balance
                      FROM %(from_clause)s
                      %(currency_join)s
                     WHERE %(where_clause)s
                       AND account_move_line.account_id IN %(account_ids)s
                  GROUP BY account_move_line.account_id
                """,
                balance=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                from_clause=query.from_clause,
                currency_join=report._currency_table_aml_join(column_options),
                where_clause=query.where_clause,
                account_ids=tuple(accounts.ids) or (0,),
            ))
            balances_by_group[group_key] = {
                row["account_id"]: row["balance"]
                for row in self.env.cr.dictfetchall()
            }

        lines = []
        for account in ordered_accounts:
            columns = [report._build_column_dict(
                balances_by_group[column["column_group_key"]].get(account.id, 0.0),
                column,
                options=options,
            ) for column in options["columns"]]
            lines.append({
                "id": report._get_generic_line_id(
                    "account.account", account.id, parent_line_id=line_dict_id,
                ),
                "parent_id": line_dict_id,
                "name": f"{account.code} {account.name}",
                "level": report_line.hierarchy_level + 2,
                "columns": columns,
                "caret_options": "account.account",
            })
        return {
            "lines": lines,
            "offset_increment": len(lines),
            "has_more": False,
        }


class VhgBalanceSheetSummaryReportHandler(VhgBalanceSheetReportBase):
    _name = "tha.vhg.balance.sheet.summary.report.handler"
    _description = "VHG Balance Sheet Summary Report Handler"
    _REPORT_TITLE = "Management Balance Sheet Summary"

    _SUMMARY_LINES = (
        ("VHG_BS_ASSETS_SECTION", 0),
        ("VHG_BS_NCA_SECTION", 1),
        ("VHG_BS_PPE", 2),
        ("VHG_BS_INTANGIBLE", 2),
        ("VHG_BS_OTHER_NCA_SECTION", 1),
        ("VHG_BS_INVESTMENT", 2),
        ("VHG_BS_CONSTRUCTION", 2),
        ("VHG_BS_CA_SECTION", 1),
        ("VHG_BS_CASH", 2),
        ("VHG_BS_BANK", 2),
        ("VHG_BS_RECEIVABLES", 2),
        ("VHG_BS_INVENTORY", 2),
        ("VHG_BS_PREPAYMENTS", 2),
        ("VHG_BS_ADVANCED_TAX", 2),
        ("VHG_BS_OTHER_ASSETS", 2),
        ("VHG_BS_EL_SECTION", 0),
        ("VHG_BS_EQUITY_SECTION", 1),
        ("VHG_BS_SHARE_CAPITAL", 2),
        ("VHG_BS_DIVIDEND", 2),
        ("RET_EARN", 2),
        ("Cur_Yr_PL", 2),
        ("VHG_BS_LIABILITY_SECTION", 1),
        ("VHG_BS_NCL", 2),
        ("VHG_BS_CL_SECTION", 2),
        ("VHG_BS_TRADE_PAYABLES", 3),
        ("VHG_BS_DEFERRED", 3),
        ("VHG_BS_TAX_PAYABLE", 3),
        ("VHG_BS_OTHER_PAYABLE", 3),
        ("VHG_BS_OFF_BALANCE", 0),
    )

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None,
    ):
        """Reuse Notes values so mappings and formulas have one source of truth."""
        notes_report = self.env.ref(
            "tha_vhg_bs_ext.report_vhg_balance_sheet_notes"
        ).with_context(self.env.context).with_company(self.env.company)
        notes_options = notes_report.get_options(options)
        notes_lines = notes_report._get_lines(notes_options)
        source_records = {
            line.code: line
            for line in self.env["account.report.line"].search([
                ("report_id", "=", notes_report.id),
            ])
        }
        source_lines = {}
        for line in notes_lines:
            model, record_id = notes_report._get_model_info_from_id(line["id"])
            if model == "account.report.line":
                source = self.env[model].browse(record_id)
                source_lines.setdefault(source.code, line)

        result = []
        for code, level in self._SUMMARY_LINES:
            source = source_lines.get(code, {
                "name": source_records[code].name,
                "columns": [report._build_column_dict(
                    0.0, column, options=options,
                ) for column in options["columns"]],
            })
            line = {
                **source,
                "id": report._get_generic_line_id(
                    None, None, markup=f"vhg_bs_summary_{code.lower()}"
                ),
                "level": level,
                "class": "fw-bold" if level <= 1 else "",
                "unfoldable": False,
                "unfolded": False,
            }
            for key in ("parent_id", "expand_function", "groupby"):
                line.pop(key, None)
            result.append((0, line))
        return result
