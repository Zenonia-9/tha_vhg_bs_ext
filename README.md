# VHG Balance Sheet Extension

Adds workbook/source-aligned Management Balance Sheet Notes & Summary and Management
Balance Sheet Summary reports below Accounting > Configuration > Management Reports.

The standalone addon depends only on Odoo's `account_reports`; it supplies its
own Management Reports menu, report header, and styling. The handlers keep account classifications centralized in Python, support
comparison periods and multi-company selection, and expose mapped accounts by
unfolding Notes lines.
