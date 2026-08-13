# -*- coding: utf-8 -*-
"""Balance Sheet-specific reporting options."""

from dateutil.relativedelta import relativedelta

from odoo import fields, models


class AccountReport(models.Model):
    _inherit = "account.report"

    def _tha_vhg_is_balance_sheet_report(self):
        """Keep the comparison-date adjustment strictly local to this addon."""
        report_ids = {
            self.env.ref(xmlid, raise_if_not_found=False).id
            for xmlid in (
                "tha_vhg_bs_ext.report_vhg_balance_sheet_notes",
                "tha_vhg_bs_ext.report_vhg_balance_sheet_summary",
            )
        }
        report_ids.discard(False)
        return bool(self.ids) and set(self.ids).issubset(report_ids)

    def _get_shifted_dates_period(self, options, period_vals, periods, return_period=False):
        """Compare an as-of Balance Sheet date with preceding month ends.

        Odoo's generic ``today`` filter moves to the preceding fiscal year,
        which turns 13 Aug into 31 Mar for this company's April fiscal year.
        Balance Sheet comparisons are as-of snapshots, so one previous period
        must instead be 31 Jul.
        """
        if (
            not self._tha_vhg_is_balance_sheet_report()
            or period_vals.get("mode") != "single"
            or periods >= 0
            or return_period
        ):
            return super()._get_shifted_dates_period(
                options, period_vals, periods, return_period=return_period,
            )

        period_end = fields.Date.to_date(period_vals["date_to"])
        previous_month_end = (
            period_end.replace(day=1)
            + relativedelta(months=periods + 1, days=-1)
        )
        fiscalyear_start = self.env.company.compute_fiscalyear_dates(
            previous_month_end
        )["date_from"]
        return self._get_dates_period(
            fiscalyear_start, previous_month_end, "single", period_type="custom",
        )
