"""
seed_payroll.py — one-off script to populate payroll_tax_brackets_dev and
payroll_settings_dev with the 2026 Israeli payroll values.

Run via:
    python manage.py shell < seed_payroll.py

Or alternatively, paste the body into a `python manage.py shell` session.

Idempotent: only inserts rows that don't already exist. Safe to re-run.

When the law changes, edit the values via Django admin (/admin/core/payrolltaxbracket/
and /admin/core/payrollsetting/) — DON'T re-run this script with edited values,
because it won't update existing rows.

Sources for 2026 numbers:
  - רשות המסים — לוח עזר ינואר 2026
  - חוק ריווח מדרגות מס פורסם 31.3.2026, רטרואקטיבי מ-1.1.2026
  - ביטוח לאומי — חוזר מעסיקים 1522 (1.2026)
  - kolzchut.org.il, malam-payroll.com
"""

from decimal import Decimal
from core.models import PayrollTaxBracket, PayrollSetting


# ─── Tax brackets (post-31.3.2026 widening) ──────────────────────────────

BRACKETS = [
    # (bracket_index, ceiling_or_None, rate, notes)
    (1, Decimal('7010'),  Decimal('0.10'), 'מדרגה ראשונה'),
    (2, Decimal('10060'), Decimal('0.14'), ''),
    (3, Decimal('19000'), Decimal('0.20'), 'הורחבה מ-16,150 ל-19,000 (תיקון 288)'),
    (4, Decimal('25100'), Decimal('0.31'), 'הורחבה מ-22,440 ל-25,100 (תיקון 288)'),
    (5, Decimal('44550'), Decimal('0.35'), ''),
    (6, Decimal('57360'), Decimal('0.47'), ''),
    (7, None,             Decimal('0.50'), 'כולל מס יסף 3%'),
]


# ─── Scalar settings (BL, health, credit point, defaults) ───────────────

SETTINGS = [
    # (setting_key, value, notes)
    ('tax_credit_point_value',   Decimal('242.000000'),  'ערך נקודת זיכוי בש"ח לחודש (קפוא 2024-2027)'),

    ('bl_threshold',             Decimal('7703.000000'), 'סף ביטוח לאומי 2026 (60% מהשכר הממוצע)'),
    ('bl_upper_ceiling',         Decimal('51910.000000'), 'תקרה עליונה לבל"ל 2026 (פי 8 מהשכר הממוצע)'),
    ('bl_employee_low',          Decimal('0.010400'),    'בל"ל עובד מתחת לסף — 1.04%'),
    ('bl_employee_high',         Decimal('0.070000'),    'בל"ל עובד מעל לסף — 7%'),
    ('bl_employer_low',          Decimal('0.045100'),    'בל"ל מעסיק מתחת לסף — 4.51%'),
    ('bl_employer_high',         Decimal('0.076000'),    'בל"ל מעסיק מעל לסף — 7.6%'),

    ('health_threshold',         Decimal('7703.000000'), 'סף ביטוח בריאות 2026'),
    ('health_employee_low',      Decimal('0.032300'),    'בריאות מתחת לסף — 3.23%'),
    ('health_employee_high',     Decimal('0.051700'),    'בריאות מעל לסף — 5.17%'),

    ('default_pension_employee', Decimal('6.000000'),    'פנסיה ברירת-מחדל עובד (אחוזים)'),
    ('default_pension_employer', Decimal('6.500000'),    'פנסיה ברירת-מחדל מעסיק (אחוזים)'),
    ('default_severance',        Decimal('8.330000'),    'פיצויים ברירת-מחדל (אחוזים)'),
    ('default_study_employee',   Decimal('2.500000'),    'קרן השתלמות ברירת-מחדל עובד (אחוזים)'),
    ('default_study_employer',   Decimal('7.500000'),    'קרן השתלמות ברירת-מחדל מעסיק (אחוזים)'),
]


# ─── Run ─────────────────────────────────────────────────────────────────

print("=" * 60)
print("Seeding payroll data (2026)")
print("=" * 60)

# Brackets
print("\nTax brackets:")
created_brackets = 0
existing_brackets = 0
for idx, ceiling, rate, notes in BRACKETS:
    obj, created = PayrollTaxBracket.objects.get_or_create(
        bracket_index=idx,
        defaults={
            'ceiling': ceiling,
            'rate':    rate,
            'notes':   notes,
        }
    )
    if created:
        created_brackets += 1
        ceil_str = f'₪{ceiling:,.0f}' if ceiling else '∞'
        print(f"  + Bracket {idx}: ≤ {ceil_str} → {float(rate)*100:g}%")
    else:
        existing_brackets += 1
        print(f"  · Bracket {idx} already exists, skipped")

# Settings
print("\nSettings:")
created_settings = 0
existing_settings = 0
for key, value, notes in SETTINGS:
    obj, created = PayrollSetting.objects.get_or_create(
        setting_key=key,
        defaults={
            'setting_value': value,
            'notes':         notes,
        }
    )
    if created:
        created_settings += 1
        print(f"  + {key} = {value}")
    else:
        existing_settings += 1
        print(f"  · {key} already exists, skipped")

print()
print("=" * 60)
print(f"Done. Brackets: {created_brackets} created, {existing_brackets} skipped")
print(f"      Settings: {created_settings} created, {existing_settings} skipped")
print("=" * 60)
print()
print("To edit values later, use Django admin:")
print("  /admin/core/payrolltaxbracket/")
print("  /admin/core/payrollsetting/")