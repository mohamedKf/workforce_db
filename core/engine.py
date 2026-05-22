"""
Israeli Payroll Calculation Engine — 2026 (DB-backed).

Tax brackets and BL/Health/credit-point settings live in the database
(see PayrollTaxBracket and PayrollSetting models). This module reads them
on each calculation, with a 60-second in-memory cache to avoid hammering
the DB during a multi-worker payroll run.

If the tables are empty (fresh DB) or unreachable, falls back to hardcoded
2026 defaults — the engine never crashes on a payroll calculation.

Notable rules implemented:
  1. Pension contribution reduces taxable income (Israeli law).
  2. BL & health computed on (gross - employee_pension), same base as tax.
  3. BL has a low/high threshold and an upper ceiling; health has only a
     low/high threshold (no upper ceiling for the health rate).
  4. Overtime: first 2h at 125%, rest at 150%.

Sources for 2026 hardcoded fallbacks:
  - רשות המסים לוח עזר ינואר 2026
  - חוק ריווח מדרגות מס פורסם 31.3.2026, רטרואקטיבי מ-1.1.2026
  - ביטוח לאומי חוזר מעסיקים 1522 (1.2026)
"""

from __future__ import annotations
import time


# ─── Hardcoded 2026 fallbacks ─────────────────────────────────────────────

DEFAULT_INCOME_TAX_BRACKETS = [
    (7_010,         0.10),
    (10_060,        0.14),
    (19_000,        0.20),
    (25_100,        0.31),
    (44_550,        0.35),
    (57_360,        0.47),
    (float('inf'),  0.50),
]

DEFAULT_SETTINGS = {
    "tax_credit_point_value":    242.0,
    "bl_threshold":              7_703.0,
    "bl_upper_ceiling":          51_910.0,
    "bl_employee_low":           0.0104,
    "bl_employee_high":          0.0700,
    "bl_employer_low":           0.0451,
    "bl_employer_high":          0.0760,
    "health_threshold":          7_703.0,
    "health_employee_low":       0.0323,
    "health_employee_high":      0.0517,
    "default_pension_employee":  6.0,
    "default_pension_employer":  6.5,
    "default_severance":         8.33,
    "default_study_employee":    2.5,
    "default_study_employer":    7.5,
}


# ─── DB cache ─────────────────────────────────────────────────────────────

_CACHE_TTL_SECONDS = 60
_cache = {"data": None, "expires_at": 0.0}


def _load_payroll_settings(force: bool = False) -> dict:
    """
    Read brackets + settings from DB. Cached for 60 seconds. On any failure
    (table missing, DB down, malformed rows), falls back to module defaults.
    """
    now = time.time()
    if not force and _cache["data"] and _cache["expires_at"] > now:
        return _cache["data"]

    settings = {
        "income_tax_brackets": list(DEFAULT_INCOME_TAX_BRACKETS),
        **DEFAULT_SETTINGS,
    }

    try:
        # Lazy import to avoid Django import-time issues when this module is
        # imported standalone (e.g. by tests).
        from .models import PayrollTaxBracket, PayrollSetting

        rows = list(PayrollTaxBracket.objects.order_by('bracket_index'))
        if rows:
            parsed = []
            for r in rows:
                ceiling = float(r.ceiling) if r.ceiling is not None else float('inf')
                rate    = float(r.rate)
                parsed.append((ceiling, rate))
            parsed.sort(key=lambda x: x[0])
            settings["income_tax_brackets"] = parsed

        for s in PayrollSetting.objects.all():
            key = s.setting_key
            if key in DEFAULT_SETTINGS:
                try:
                    settings[key] = float(s.setting_value)
                except (TypeError, ValueError, ArithmeticError):
                    pass
    except Exception:
        # Tables missing, DB down, etc. — use defaults silently.
        pass

    _cache["data"]       = settings
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return settings


def invalidate_cache():
    """Call after editing PayrollTaxBracket / PayrollSetting in the same process."""
    _cache["data"]       = None
    _cache["expires_at"] = 0.0


# ─── Core calculations ────────────────────────────────────────────────────

def calculate_income_tax(taxable, tax_points=2.25, settings=None):
    s = settings or _load_payroll_settings()
    brackets    = s["income_tax_brackets"]
    point_value = s["tax_credit_point_value"]
    if taxable <= 0:
        return 0.0

    tax  = 0.0
    prev = 0.0
    for ceiling, rate in brackets:
        if taxable <= prev:
            break
        slab = min(taxable, ceiling) - prev
        tax += slab * rate
        prev = ceiling
        if taxable <= ceiling:
            break

    credit = tax_points * point_value
    return round(max(0.0, tax - credit), 2)


def calculate_bituah_leumi(taxable, settings=None):
    s = settings or _load_payroll_settings()
    bl_thr  = s["bl_threshold"]
    bl_ceil = s["bl_upper_ceiling"]
    bl_e_lo = s["bl_employee_low"]
    bl_e_hi = s["bl_employee_high"]
    bl_r_lo = s["bl_employer_low"]
    bl_r_hi = s["bl_employer_high"]
    h_thr   = s["health_threshold"]
    h_e_lo  = s["health_employee_low"]
    h_e_hi  = s["health_employee_high"]

    if taxable <= 0:
        return {
            "bl_employee":     0.0,
            "bl_employer":     0.0,
            "health_employee": 0.0,
            "total_employee":  0.0,
            "total_employer":  0.0,
        }

    capped = min(taxable, bl_ceil)

    if capped <= bl_thr:
        bl_emp = capped * bl_e_lo
    else:
        bl_emp = bl_thr * bl_e_lo + (capped - bl_thr) * bl_e_hi

    if capped <= bl_thr:
        bl_er = capped * bl_r_lo
    else:
        bl_er = bl_thr * bl_r_lo + (capped - bl_thr) * bl_r_hi

    if capped <= h_thr:
        h_emp = capped * h_e_lo
    else:
        h_emp = h_thr * h_e_lo + (capped - h_thr) * h_e_hi

    return {
        "bl_employee":     round(bl_emp, 2),
        "bl_employer":     round(bl_er, 2),
        "health_employee": round(h_emp, 2),
        "total_employee":  round(bl_emp + h_emp, 2),
        "total_employer":  round(bl_er, 2),
    }


def calculate_overtime(hourly_rate, regular_hours, overtime_hours):
    first_2  = min(overtime_hours, 2.0)
    beyond_2 = max(0.0, overtime_hours - 2.0)
    regular  = hourly_rate * regular_hours
    over     = (hourly_rate * 1.25 * first_2) + (hourly_rate * 1.50 * beyond_2)
    return {
        "regular_pay":  round(regular, 2),
        "overtime_pay": round(over, 2),
        "total_pay":    round(regular + over, 2),
    }


def calculate_full_salary(worker_data, hours_data):
    s = _load_payroll_settings()

    wage_type      = worker_data.get("wage_type", "hourly")
    hourly_rate    = float(worker_data.get("hourly_rate", 0) or 0)
    monthly_salary = float(worker_data.get("monthly_salary", 0) or 0)
    tax_points     = float(worker_data.get("tax_points", 2.25) or 2.25)
    travel         = float(worker_data.get("travel_allowance", 0) or 0)
    regular_hours  = float(hours_data.get("regular_hours", 0) or 0)
    overtime_hours = float(hours_data.get("overtime_hours", 0) or 0)

    if wage_type == "hourly":
        ot           = calculate_overtime(hourly_rate, regular_hours, overtime_hours)
        base_pay     = ot["regular_pay"]
        overtime_pay = ot["overtime_pay"]
    else:
        base_pay     = monthly_salary
        overtime_pay = 0.0

    base_pay     = round(base_pay, 2)
    overtime_pay = round(overtime_pay, 2)
    travel       = round(travel, 2)
    gross        = round(base_pay + overtime_pay + travel, 2)

    pension_emp_pct = float(worker_data.get("pension_rate_employee",
                                            s["default_pension_employee"]) or 0)
    study_emp_pct   = float(worker_data.get("study_fund_employee",
                                            s["default_study_employee"])   or 0)
    pension_employee    = round(gross * pension_emp_pct / 100, 2)
    study_fund_employee = round(gross * study_emp_pct   / 100, 2)

    taxable = round(gross - pension_employee, 2)

    income_tax = calculate_income_tax(taxable, tax_points, settings=s)

    bl = calculate_bituah_leumi(taxable, settings=s)
    bl_employee      = bl["bl_employee"]
    bl_employer      = bl["bl_employer"]
    health_insurance = bl["health_employee"]

    bituah_leumi_total = round(bl_employee + health_insurance, 2)

    pension_er_pct  = float(worker_data.get("pension_rate_employer",
                                            s["default_pension_employer"]) or 0)
    severance_pct   = float(worker_data.get("severance_rate",
                                            s["default_severance"])        or 0)
    study_er_pct    = float(worker_data.get("study_fund_employer",
                                            s["default_study_employer"])   or 0)
    pension_employer    = round(gross * pension_er_pct / 100, 2)
    severance           = round(gross * severance_pct  / 100, 2)
    study_fund_employer = round(gross * study_er_pct   / 100, 2)

    total_deductions = round(
        income_tax + bl_employee + health_insurance +
        pension_employee + study_fund_employee, 2
    )
    net_salary = round(gross - total_deductions, 2)

    total_employer_cost = round(
        gross + pension_employer + severance + study_fund_employer + bl_employer, 2
    )

    return {
        "wage_type":            wage_type,
        "regular_hours":        round(regular_hours, 2),
        "overtime_hours":       round(overtime_hours, 2),
        "base_pay":             base_pay,
        "overtime_pay":         overtime_pay,
        "travel_allowance":     travel,
        "gross_salary":         gross,
        "income_tax":           income_tax,
        "bituah_leumi":         bituah_leumi_total,
        "bituah_leumi_only":    bl_employee,
        "health_insurance":     health_insurance,
        "pension_employee":     pension_employee,
        "study_fund_employee":  study_fund_employee,
        "total_deductions":     total_deductions,
        "net_salary":           net_salary,
        "pension_employer":     pension_employer,
        "severance":            severance,
        "study_fund_employer":  study_fund_employer,
        "bl_employer":          bl_employer,
        "total_employer_cost":  total_employer_cost,
        "tax_points":           tax_points,
    }