"""
Israeli Payroll Calculation Engine — 2024
"""

# ── Tax brackets ───────────────────────────────────────────────────────────
INCOME_TAX_BRACKETS = [
    (7010,         0.10),
    (10060,        0.14),
    (16150,        0.20),
    (21420,        0.31),
    (44550,        0.35),
    (57360,        0.47),
    (float('inf'), 0.50),
]

TAX_CREDIT_POINT_VALUE   = 235      # ₪ per month (2024)
BITUAH_LEUMI_THRESHOLD   = 7522
BITUAH_LEUMI_UPPER_LIMIT = 49030
BITUAH_LEUMI_RATE_LOW    = 0.004
BITUAH_LEUMI_RATE_HIGH   = 0.07
HEALTH_THRESHOLD         = 7522
HEALTH_RATE_LOW          = 0.031
HEALTH_RATE_HIGH         = 0.05


def calculate_income_tax(gross: float, tax_points: float = 2.25) -> float:
    tax, prev = 0.0, 0.0
    for limit, rate in INCOME_TAX_BRACKETS:
        if gross <= prev:
            break
        taxable = min(gross, limit) - prev
        tax += taxable * rate
        prev = limit
        if gross <= limit:
            break
    return round(max(0.0, tax - tax_points * TAX_CREDIT_POINT_VALUE), 2)


def calculate_bituah_leumi(gross: float) -> dict:
    capped = min(gross, BITUAH_LEUMI_UPPER_LIMIT)

    if capped <= BITUAH_LEUMI_THRESHOLD:
        bl = capped * BITUAH_LEUMI_RATE_LOW
    else:
        bl = (BITUAH_LEUMI_THRESHOLD * BITUAH_LEUMI_RATE_LOW +
              (capped - BITUAH_LEUMI_THRESHOLD) * BITUAH_LEUMI_RATE_HIGH)

    if capped <= HEALTH_THRESHOLD:
        health = capped * HEALTH_RATE_LOW
    else:
        health = (HEALTH_THRESHOLD * HEALTH_RATE_LOW +
                  (capped - HEALTH_THRESHOLD) * HEALTH_RATE_HIGH)

    return {
        'bituah_leumi':    round(bl, 2),
        'health_insurance': round(health, 2),
    }


def calculate_overtime(hourly_rate: float, regular_hours: float, overtime_hours: float) -> dict:
    first_2  = min(overtime_hours, 2.0)
    beyond_2 = max(0.0, overtime_hours - 2.0)
    regular_pay  = hourly_rate * regular_hours
    overtime_pay = (hourly_rate * 1.25 * first_2) + (hourly_rate * 1.50 * beyond_2)
    return {
        'regular_pay':  round(regular_pay, 2),
        'overtime_pay': round(overtime_pay, 2),
        'total_pay':    round(regular_pay + overtime_pay, 2),
    }


def calculate_full_salary(worker_data: dict, hours_data: dict) -> dict:
    wage_type      = worker_data.get('wage_type', 'hourly')
    hourly_rate    = float(worker_data.get('hourly_rate', 0))
    monthly_salary = float(worker_data.get('monthly_salary', 0))
    tax_points     = float(worker_data.get('tax_points', 2.25))
    travel         = float(worker_data.get('travel_allowance', 0))
    regular_hours  = float(hours_data.get('regular_hours', 0))
    overtime_hours = float(hours_data.get('overtime_hours', 0))

    if wage_type == 'hourly':
        ot           = calculate_overtime(hourly_rate, regular_hours, overtime_hours)
        base_pay     = ot['regular_pay']
        overtime_pay = ot['overtime_pay']
    else:
        base_pay     = monthly_salary
        overtime_pay = 0.0

    gross = base_pay + overtime_pay + travel

    pension_employee    = round(gross * float(worker_data.get('pension_rate_employee', 6.0)) / 100, 2)
    study_fund_employee = round(gross * float(worker_data.get('study_fund_employee', 2.5)) / 100, 2)
    taxable             = gross - pension_employee
    income_tax          = calculate_income_tax(taxable, tax_points)
    insurance           = calculate_bituah_leumi(taxable)
    bituah_leumi        = insurance['bituah_leumi']
    health_insurance    = insurance['health_insurance']
    total_deductions    = pension_employee + study_fund_employee + income_tax + bituah_leumi + health_insurance
    net_salary          = round(gross - total_deductions, 2)

    pension_employer    = round(gross * float(worker_data.get('pension_rate_employer', 6.5)) / 100, 2)
    severance           = round(gross * float(worker_data.get('severance_rate', 8.33)) / 100, 2)
    study_fund_employer = round(gross * float(worker_data.get('study_fund_employer', 7.5)) / 100, 2)
    total_employer_cost = round(gross + pension_employer + severance + study_fund_employer, 2)

    return {
        'gross_salary':        round(gross, 2),
        'base_pay':            round(base_pay, 2),
        'overtime_pay':        round(overtime_pay, 2),
        'travel_allowance':    round(travel, 2),
        'regular_hours':       regular_hours,
        'overtime_hours':      overtime_hours,
        'income_tax':          income_tax,
        'bituah_leumi':        bituah_leumi,
        'health_insurance':    health_insurance,
        'pension_employee':    pension_employee,
        'study_fund_employee': study_fund_employee,
        'total_deductions':    round(total_deductions, 2),
        'net_salary':          net_salary,
        'pension_employer':    pension_employer,
        'severance':           severance,
        'study_fund_employer': study_fund_employer,
        'total_employer_cost': total_employer_cost,
    }
