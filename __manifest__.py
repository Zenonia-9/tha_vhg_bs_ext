# -*- coding: utf-8 -*-
{
    "name": "VHG Balance Sheet Extension",
    "summary": "VHG management Balance Sheet notes and summary reports.",
    "version": "19.0.1.2.3",
    "category": "Accounting/Accounting",
    "author": "Thein Htoo Aung",
    "license": "LGPL-3",
    "depends": ["account_reports"],
    "data": ["data/balance_sheet_reports.xml"],
    "assets": {
        "web.assets_backend": [
            "tha_vhg_bs_ext/static/src/components/balance_sheet_header.xml",
            "tha_vhg_bs_ext/static/src/scss/balance_sheet_report.scss",
        ],
    },
    "installable": True,
    "application": False,
}
