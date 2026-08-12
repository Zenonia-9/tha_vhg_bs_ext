# -*- coding: utf-8 -*-

from odoo import models


class AccountReport(models.Model):
    _inherit = "account.report"

    def _tha_vhg_is_balance_sheet_report(self):
        balance_sheet_reports = self.env["account.report"].browse([
            report.id
            for xmlid in (
                "tha_vhg_bs_ext.report_vhg_balance_sheet_notes",
                "tha_vhg_bs_ext.report_vhg_balance_sheet_summary",
            )
            if (report := self.env.ref(xmlid, raise_if_not_found=False))
        ])
        return self in balance_sheet_reports

    def _add_totals_below_sections(self, lines, options):
        if not self._tha_vhg_is_balance_sheet_report() or self.env.company.totals_below_sections:
            return super()._add_totals_below_sections(lines, options)
        if options.get("ignore_totals_below_sections"):
            return lines

        lines_needing_total = set()
        for line in lines:
            if self._get_markup(line["id"]) == "total":
                continue
            if line.get("unfoldable") or (line.get("unfolded") and line.get("expand_function")):
                lines_needing_total.add(line["id"])
            if line.get("parent_id"):
                lines_needing_total.add(line["parent_id"])

        lines_with_totals = []
        totals_stack = []
        for line in lines:
            while totals_stack and not line["id"].startswith(f'{totals_stack[-1]["parent_id"]}|'):
                lines_with_totals.append(totals_stack.pop())
            lines_with_totals.append(line)
            if line["id"] in lines_needing_total and any(
                column.get("no_format") is not None for column in line["columns"]
            ):
                totals_stack.append(self._generate_total_below_section_line(line))

        lines_with_totals.extend(reversed(totals_stack))
        return lines_with_totals
