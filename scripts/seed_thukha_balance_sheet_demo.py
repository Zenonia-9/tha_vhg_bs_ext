"""Create balanced, realistic-looking March--August 2026 test data for THUKHA SAYTANAR.

Run in an Odoo shell.  The script removes and recreates only moves marked
``VHG BS Demo`` so it is safe to rerun and never touches normal company data.
"""

from datetime import date


COMPANY_NAME = "THUKHA SAYTANAR CO. Ltd (Victoria Hospital)"
REF_PREFIX = "VHG BS Demo"


company = env["res.company"].search([("name", "=", COMPANY_NAME)], limit=1)
assert company, "THUKHA SAYTANAR CO. Ltd (Victoria Hospital) was not found"
journal = env["account.journal"].search([
    ("company_id", "=", company.id), ("code", "=", "MISC"),
], limit=1)
assert journal, "THUKHA SAYTANAR MISC journal was not found"


def account(name):
    record = env["account.account"].search([
        ("company_ids", "in", company.id), ("name", "=", name),
    ], limit=1)
    assert record, f"THUKHA SAYTANAR account not found: {name}"
    return record


accounts = {
    "cash": account("Cash in hand - KS (Front Office)"),
    "bank": account("A Bank -Trust Call Saving -MMK (0021011200019184)"),
    "receivable": account("Trade Receivable - Inpatient/Outpatient Receivable"),
    "inventory": account("Pharmacy"),
    "prepaid": account("Prepaid Expenses"),
    "tax_asset": account("Advance Income Tax"),
    "deposit": account("Deposit payment"),
    "ppe": account("Building & infrastructure development - gross"),
    "intangible": account("Intangible Assets"),
    "investment": account("Investment in (Innovative Diagnostics)-Subsidiary 80%"),
    "construction": account("VTR Extension-Construction-Material"),
    "payable": account("Trade payables - Supplier"),
    "other_payable": account("Payable Expense"),
    "deferred": account("Deferred Income"),
    "tax_payable": account("Income Tax Payable"),
    "loan": account("Long Term Loans"),
    "share": account("Ordinary Share"),
    "advance_share": account("Advance Capital"),
    "retained": account("Retained Earnings"),
    "income": account("Services Income"),
    "expense": account("Electricity"),
}


existing = env["account.move"].search([
    ("company_id", "=", company.id), ("ref", "=like", f"{REF_PREFIX}%"),
])
if existing:
    existing.button_draft()
    existing.unlink()


def post(move_date, label, entries):
    """entries are (account_key, debit, credit) and must balance."""
    debit = sum(item[1] for item in entries)
    credit = sum(item[2] for item in entries)
    assert debit == credit, f"{label} is not balanced: {debit:,} != {credit:,}"
    move = env["account.move"].create({
        "move_type": "entry",
        "date": move_date,
        "journal_id": journal.id,
        "company_id": company.id,
        "ref": f"{REF_PREFIX} | {label}",
        "line_ids": [(0, 0, {
            "name": label,
            "account_id": accounts[key].id,
            "debit": debit_amount,
            "credit": credit_amount,
        }) for key, debit_amount, credit_amount in entries],
    })
    move.action_post()
    return move


# Opening financial position, as at the beginning of March.
post(date(2026, 3, 1), "Opening position", [
    ("cash", 45_000_000, 0), ("bank", 620_000_000, 0),
    ("receivable", 180_000_000, 0), ("inventory", 95_000_000, 0),
    ("prepaid", 24_000_000, 0), ("tax_asset", 12_000_000, 0),
    ("deposit", 9_000_000, 0), ("ppe", 1_150_000_000, 0),
    ("intangible", 85_000_000, 0), ("investment", 140_000_000, 0),
    ("construction", 210_000_000, 0),
    ("payable", 0, 120_000_000), ("other_payable", 0, 38_000_000),
    ("deferred", 0, 28_000_000), ("tax_payable", 0, 16_000_000),
    ("loan", 0, 460_000_000), ("share", 0, 1_400_000_000),
    ("advance_share", 0, 200_000_000), ("retained", 0, 308_000_000),
])

monthly = (
    # month, service billed, collection, stock received, supplier payment,
    # payroll/utilities, capital work, prepaid, tax payment, deposit, deferred receipt
    (3, 118_000_000, 92_000_000, 31_000_000, 42_000_000, 21_000_000, 18_000_000, 4_500_000, 2_000_000, 0, 10_000_000),
    (4, 126_000_000, 108_000_000, 34_000_000, 46_000_000, 22_500_000, 12_000_000, 3_000_000, 2_500_000, 3_000_000, 8_000_000),
    (5, 132_000_000, 120_000_000, 29_000_000, 39_000_000, 24_000_000, 20_000_000, 5_000_000, 2_000_000, 0, 12_000_000),
    (6, 128_000_000, 123_000_000, 36_000_000, 48_000_000, 23_000_000, 15_000_000, 3_500_000, 3_000_000, 2_000_000, 9_000_000),
    (7, 139_000_000, 131_000_000, 33_000_000, 45_000_000, 25_000_000, 22_000_000, 4_000_000, 2_500_000, 0, 11_000_000),
    (8, 145_000_000, 136_000_000, 38_000_000, 52_000_000, 26_000_000, 16_000_000, 4_500_000, 3_000_000, 4_000_000, 10_000_000),
)

created = []
for month, billed, collected, stock, supplier_paid, expense, capital, prepaid, tax, deposit, deferred in monthly:
    month_end = date(2026, month, 28)
    created.extend([
        post(month_end, f"{month:02d}/2026 service billing", [("receivable", billed, 0), ("income", 0, billed)]),
        post(month_end, f"{month:02d}/2026 patient collections", [("bank", collected, 0), ("receivable", 0, collected)]),
        post(month_end, f"{month:02d}/2026 pharmacy replenishment", [("inventory", stock, 0), ("payable", 0, stock)]),
        post(month_end, f"{month:02d}/2026 supplier settlement", [("payable", supplier_paid, 0), ("bank", 0, supplier_paid)]),
        post(month_end, f"{month:02d}/2026 utilities and operations", [("expense", expense, 0), ("bank", 0, expense)]),
        post(month_end, f"{month:02d}/2026 construction progress", [("construction", capital, 0), ("bank", 0, capital)]),
        post(month_end, f"{month:02d}/2026 annual insurance prepayment", [("prepaid", prepaid, 0), ("bank", 0, prepaid)]),
        post(month_end, f"{month:02d}/2026 advance income tax", [("tax_asset", tax, 0), ("bank", 0, tax)]),
    ])
    if deposit:
        created.append(post(month_end, f"{month:02d}/2026 security deposit", [("deposit", deposit, 0), ("bank", 0, deposit)]))
    created.append(post(month_end, f"{month:02d}/2026 advance service receipts", [("bank", deferred, 0), ("deferred", 0, deferred)]))

env.cr.commit()
print(f"Created {1 + len(created)} posted THUKHA SAYTANAR demo moves from March to August 2026.")
