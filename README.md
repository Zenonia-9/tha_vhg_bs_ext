# VHG Balance Sheet Extension

Adds workbook/source-aligned Management Balance Sheet Notes & Summary and Management
Balance Sheet Summary reports below Accounting > Configuration > Management Reports.

The standalone addon depends only on Odoo's `account_reports`. It owns its
reports, fallback Management Reports menu, header, and styling. Notes uses
native `account.report.line` formulas; Summary uses one scoped custom handler.
No shared `account.report` behavior is overridden.
