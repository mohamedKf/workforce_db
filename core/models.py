from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


# ── User Manager ───────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    def create_user(self, id_number, password=None, **extra_fields):
        if not id_number:
            raise ValueError('ID number is required')
        user = self.model(id_number=id_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, id_number, password=None, **extra_fields):
        extra_fields.setdefault('role', 'manager')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(id_number, password, **extra_fields)


# ── User ───────────────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('owner', 'בעלים'),
        ('manager', 'מנהל'),
        ('worker', 'עובד'),
        ('freelancer', 'פרילנסר'),
    ]


    id_number            = models.CharField(max_length=20, unique=True)
    phone                = models.CharField(max_length=20, blank=True)
    full_name            = models.CharField(max_length=100)
    role                 = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')
    is_active            = models.BooleanField(default=True)
    is_staff             = models.BooleanField(default=False)

    # Fast login
    pin_code             = models.CharField(max_length=128, blank=True)
    device_token         = models.TextField(blank=True)
    device_token_expires = models.DateTimeField(null=True, blank=True)

    # Remember me token
    session_token        = models.TextField(blank=True)
    session_expires      = models.DateTimeField(null=True, blank=True)

    created_at           = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = 'id_number'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table     = 'users_dev'
        verbose_name = 'משתמש'

    def __str__(self):
        return f"{self.full_name} ({self.role})"

    @property
    def is_manager(self):
        return self.role == 'manager'

    @property
    def is_worker(self):
        return self.role == 'worker'

    @property
    def is_freelancer(self):
        return self.role == 'freelancer'

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_manager_or_above(self):
        return self.role in ['owner', 'manager']


# ── Company (for registration codes) ──────────────────────────────────────

class Company(models.Model):
    name             = models.CharField(max_length=200)
    registration_code= models.CharField(max_length=20, unique=True)  # code given to new managers
    owner            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_companies')
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'companies_dev'

    def __str__(self):
        return self.name


# ── Worker ─────────────────────────────────────────────────────────────────

class Worker(models.Model):
    GENDER_CHOICES    = [('זכר', 'זכר'), ('נקבה', 'נקבה')]
    WAGE_TYPE_CHOICES = [('hourly', 'שעתי'), ('daily', 'יומי'), ('monthly', 'חודשי')]
    MARITAL_CHOICES   = [
        ('רווק', 'רווק'), ('נשוי', 'נשוי'),
        ('גרוש', 'גרוש'), ('אלמן', 'אלמן'),
    ]

    user                     = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='worker_profile')
    company                  = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='workers')

    # Personal
    first_name               = models.CharField(max_length=100)
    last_name                = models.CharField(max_length=100)
    id_number                = models.CharField(max_length=20, unique=True)
    gender                   = models.CharField(max_length=10, choices=GENDER_CHOICES)
    birth_date               = models.DateField(null=True, blank=True)
    marital_status           = models.CharField(max_length=20, choices=MARITAL_CHOICES, default='רווק')

    # Spouse
    spouse_name              = models.CharField(max_length=200, blank=True)
    spouse_id_number         = models.CharField(max_length=20, blank=True)
    spouse_has_income        = models.BooleanField(default=False)

    # Contact
    phone                    = models.CharField(max_length=20)
    email                    = models.EmailField(blank=True)
    address                  = models.TextField(blank=True)
    city                     = models.CharField(max_length=100, blank=True)
    postal_code              = models.CharField(max_length=20, blank=True)

    # Employment
    start_date               = models.DateField()
    end_date                 = models.DateField(null=True, blank=True)
    position                 = models.CharField(max_length=100, blank=True)
    department               = models.CharField(max_length=100, blank=True)
    is_primary_employer      = models.BooleanField(default=True)

    # Wage
    wage_type                = models.CharField(max_length=10, choices=WAGE_TYPE_CHOICES, default='hourly')
    hourly_rate              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    daily_rate               = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_salary           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    travel_allowance         = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Tax
    tax_points               = models.DecimalField(max_digits=5, decimal_places=2, default=2.25)
    tax_file_number          = models.CharField(max_length=20, blank=True)
    receives_child_allowance = models.BooleanField(default=False)
    has_disabled_relative    = models.BooleanField(default=False)
    has_other_income         = models.BooleanField(default=False)

    # Pension & funds

    has_pension = models.BooleanField(default=False)
    has_study_fund = models.BooleanField(default=False)

    pension_rate_employee    = models.DecimalField(max_digits=5, decimal_places=2, default=6.0)
    pension_rate_employer    = models.DecimalField(max_digits=5, decimal_places=2, default=6.5)
    severance_rate           = models.DecimalField(max_digits=5, decimal_places=2, default=8.33)
    study_fund_employee      = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    study_fund_employer      = models.DecimalField(max_digits=5, decimal_places=2, default=7.5)

    # Bank
    bank_name                = models.CharField(max_length=50, blank=True)
    bank_branch              = models.CharField(max_length=10, blank=True)
    bank_account             = models.CharField(max_length=20, blank=True)

    is_active                = models.BooleanField(default=True)
    notes                    = models.TextField(blank=True)
    created_at               = models.DateTimeField(auto_now_add=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'workers_dev'
        verbose_name = 'עובד'

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name} ({self.id_number})"

    def calculate_tax_points(self):

        from datetime import date
        points = 2.25
        if self.gender == 'נקבה':
            points += 0.5
        for child in sorted(self.children.all(), key=lambda c: c.birth_date, reverse=True):
            age = (date.today() - child.birth_date).days // 365
            if self.gender == 'נקבה':
                if age < 1:   points += 1.5
                elif age <= 5: points += 2.5
                elif age <= 17: points += 1.0
            else:
                if age < 1:   points += 1.5
                elif age <= 5: points += 2.0
                elif age <= 17: points += 1.0
        if self.has_disabled_relative:
            points += 0.5
        return round(points, 2)


# ── Worker Child ───────────────────────────────────────────────────────────

class WorkerChild(models.Model):
    GENDER_CHOICES = [("זכר", "זכר"), ("נקבה", "נקבה")]

    worker             = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="children")
    id_number          = models.CharField(max_length=50, blank=True)
    name               = models.CharField(max_length=255, blank=True)
    birth_date         = models.DateField()
    gender             = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    receives_allowance = models.BooleanField(default=False)
    has_disability     = models.BooleanField(default=False)
    lives_with_parent  = models.BooleanField(default=True)
    custody_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    created_at         = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = "children_dev"
        ordering = ["birth_date"]

    def __str__(self):
        return f"{self.name or 'ילד'} של {self.worker.full_name}"


# ── Form 101 ───────────────────────────────────────────────────────────────

class Form101(models.Model):
    worker                   = models.OneToOneField(Worker, on_delete=models.CASCADE, related_name='form_101')
    first_name               = models.CharField(max_length=100, blank=True)
    last_name                = models.CharField(max_length=100, blank=True)
    id_number                = models.CharField(max_length=50, blank=True)
    birth_date               = models.DateField(null=True, blank=True)
    gender                   = models.CharField(max_length=10, blank=True)
    marital_status           = models.CharField(max_length=20, blank=True)
    spouse_name              = models.CharField(max_length=255, blank=True)
    spouse_id_number         = models.CharField(max_length=50, blank=True)
    spouse_income            = models.BooleanField(default=False)
    address                  = models.CharField(max_length=500, blank=True)
    city                     = models.CharField(max_length=100, blank=True)
    postal_code              = models.CharField(max_length=20, blank=True)
    phone                    = models.CharField(max_length=50, blank=True)
    email                    = models.CharField(max_length=255, blank=True)
    employment_start_date    = models.DateField(null=True, blank=True)
    is_primary_employer      = models.BooleanField(default=True)
    receives_child_allowance = models.BooleanField(default=False)
    has_disabled_relative    = models.BooleanField(default=False)
    has_other_income         = models.BooleanField(default=False)
    signed_date              = models.DateField(null=True, blank=True)
    created_at               = models.DateTimeField(auto_now_add=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_101_dev'

    def __str__(self):
        return f"טופס 101 - {self.worker.full_name}"


# ── Form 106 ───────────────────────────────────────────────────────────────

class Form106(models.Model):
    worker                        = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='form_106_records')
    tax_year                      = models.IntegerField()
    gross_income                  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_net_income              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_deducted                  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    national_insurance            = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    health_insurance              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_contribution          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_pension_contribution = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    study_fund_contribution       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax_credits             = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_date                   = models.DateField(null=True, blank=True)
    created_at                    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'form_106_dev'
        unique_together = ('worker', 'tax_year')
        ordering        = ['-tax_year']

    def __str__(self):
        return f"טופס 106 - {self.worker.full_name} - {self.tax_year}"


# ── Project ────────────────────────────────────────────────────────────────

class Project(models.Model):
    STATUS_CHOICES = [
        ('active', 'פעיל'), ('completed', 'הושלם'),
        ('on_hold', 'מושהה'), ('cancelled', 'בוטל'),
    ]

    company           = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    name              = models.CharField(max_length=200)
    description       = models.TextField(blank=True)
    client_name       = models.CharField(max_length=200, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Location
    site_lat          = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    site_lng          = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    site_address      = models.TextField(blank=True)
    gps_radius_m      = models.IntegerField(default=200)

    # Dates
    start_date        = models.DateField(null=True, blank=True)
    end_date          = models.DateField(null=True, blank=True)
    estimated_end_date= models.DateField(null=True, blank=True)  # זמן משוער לסיום

    # Budget & costs (all optional, auto-calculated where possible)
    estimated_budget  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # תקציב משוער
    workers_cost      = models.DecimalField(max_digits=12, decimal_places=2, default=0)              # עלות עובדים (מחושב)
    freelancers_cost  = models.DecimalField(max_digits=12, decimal_places=2, default=0)              # עלות פרילנסרים (מחושב)
    materials_cost    = models.DecimalField(max_digits=12, decimal_places=2, default=0)              # עלות חומרים (מחושב)
    extra_costs       = models.DecimalField(max_digits=12, decimal_places=2, default=0)              # הוצאות נוספות (ידני)
    extra_costs_notes = models.TextField(blank=True)

    # Assignments
    workers           = models.ManyToManyField(Worker, related_name='projects', blank=True)
    freelancers       = models.ManyToManyField('Freelancer', related_name='projects', blank=True)

    notes             = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects_dev'

    def __str__(self):
        return self.name

    @property
    def total_cost(self):
        return float(self.workers_cost or 0) + float(self.freelancers_cost or 0) + \
               float(self.materials_cost or 0) + float(self.extra_costs or 0)

    @property
    def budget_remaining(self):
        if self.estimated_budget:
            return float(self.estimated_budget) - self.total_cost
        return None


class ProjectFile(models.Model):
    FILE_TYPE_CHOICES = [
        ('blueprint', 'תכנית'),
        ('map',       'מפה'),
        ('document',  'מסמך'),
        ('image',     'תמונה'),
        ('other',     'אחר'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    # Legacy local storage — kept for backward compat, will be removed later
    file = models.FileField(upload_to='project_files/%Y/%m/', null=True, blank=True)
    # Cloudinary
    file_url = models.URLField(max_length=500, blank=True, default='')
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')

    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    description = models.TextField(blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    class Meta:
        db_table = 'project_files_dev'

    def __str__(self):
        return f"{self.project.name} - {self.file_name}"


# ── Attendance ─────────────────────────────────────────────────────────────

class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('open', 'פתוח'), ('closed', 'סגור'),
        ('approved', 'מאושר'), ('rejected', 'נדחה'),
    ]

    worker         = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='attendance')
    project        = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance')
    clock_in       = models.DateTimeField()
    clock_out      = models.DateTimeField(null=True, blank=True)
    clock_in_lat   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_in_lng   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_lat  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_lng  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    hours_worked   = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance_dev'
        ordering = ['-clock_in']

    def save(self, *args, **kwargs):
        if self.clock_in and self.clock_out:
            total = (self.clock_out - self.clock_in).total_seconds() / 3600
            self.hours_worked  = round(total, 2)
            self.overtime_hours = round(max(0, total - 8.0), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker.full_name} - {self.clock_in.date()}"


# ── Payroll Record ─────────────────────────────────────────────────────────

class PayrollRecord(models.Model):
    STATUS_CHOICES = [
        ('draft', 'טיוטה'), ('approved', 'מאושר'), ('paid', 'שולם'),
    ]

    worker               = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='payroll_records')
    month                = models.IntegerField()
    year                 = models.IntegerField()
    regular_hours        = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    overtime_hours       = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    gross_salary         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    base_pay             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_pay         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    travel_allowance     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    income_tax           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bituah_leumi         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    health_insurance     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pension_employee     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    study_fund_employee  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pension_employer     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    severance            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    study_fund_employer  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_employer_cost  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes                = models.TextField(blank=True)
    # Generated payslip PDF (uploaded to Cloudinary). Populated when the
    # manager clicks "Generate PDF" on the payroll page.
    # Generated payslip PDF (uploaded to Cloudinary). Populated when the
    # manager clicks "Generate PDF" on the payroll page.
    # null=True on payslip_url because MySQL TEXT columns cannot have a
    # default value, and the desktop's raw INSERT doesn't supply this column
    # — so it must accept NULL when no PDF has been generated yet.
    payslip_url           = models.TextField(blank=True, null=True, default=None)
    payslip_cloudinary_id = models.CharField(max_length=255, blank=True, default='')
    payslip_generated_at  = models.DateTimeField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'payroll_records_dev'
        unique_together = ('worker', 'month', 'year')
        ordering        = ['-year', '-month']

    def __str__(self):
        return f"{self.worker.full_name} - {self.month}/{self.year}"


# ── Material Invoice ───────────────────────────────────────────────────────

class MaterialInvoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'ממתין לאישור'),
        ('approved', 'מאושר'),
        ('rejected', 'נדחה'),
    ]

    # null=True so managers can create entries from desktop without being a worker
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='invoices',
                               null=True, blank=True)
    # Tracks who created the entry when it wasn't a worker (e.g. manager from desktop)
    created_by_user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='created_invoices')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    supplier_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_date = models.DateField()

    # Legacy local storage — kept for backward compat
    image = models.ImageField(upload_to='invoices/%Y/%m/', null=True, blank=True)
    pdf = models.FileField(upload_to='invoices/%Y/%m/', null=True, blank=True)
    # Cloudinary — invoice/receipt photo
    image_url = models.URLField(max_length=500, blank=True, default='')
    image_cloudinary_id = models.CharField(max_length=255, blank=True, default='')
    # Cloudinary — delivery note (תעודת משלוח)
    delivery_note_url = models.URLField(max_length=500, blank=True, default='')
    delivery_note_cloudinary_id = models.CharField(max_length=255, blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    manager_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'material_invoices_dev'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.worker.full_name} - ₪{self.amount}"


# ── Freelancer ─────────────────────────────────────────────────────────────

class Freelancer(models.Model):
    user         = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='freelancer_profile')
    company      = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='freelancers')
    full_name    = models.CharField(max_length=100)
    id_number    = models.CharField(max_length=20, unique=True)
    tax_id_number = models.CharField(max_length=20, blank=True, default='')
    # Default withholding tax rate for this freelancer. Most have a פטור and
    # default to 0; new agreements pre-fill this value but each agreement can
    # still override it per-project.
    default_withholding_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Default ניכוי מס במקור rate (%). 0 = פטור.',
    )
    phone        = models.CharField(max_length=20)
    email        = models.EmailField(blank=True)
    specialty    = models.CharField(max_length=100, blank=True)
    bank_name    = models.CharField(max_length=50, blank=True)
    bank_branch  = models.CharField(max_length=10, blank=True)
    bank_account = models.CharField(max_length=20, blank=True)
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'freelancers_dev'

    def __str__(self):
        return self.full_name


# ── Freelancer Agreement (per project) ────────────────────────────────────

class FreelancerAgreement(models.Model):
    """Tracks the agreement between a freelancer and a project."""
    STATUS_CHOICES = [
        ('active',    'פעיל'),
        ('completed', 'הושלם'),
        ('cancelled', 'בוטל'),
    ]

    freelancer          = models.ForeignKey(Freelancer, on_delete=models.CASCADE, related_name='agreements')
    project             = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='freelancer_agreements')
    description         = models.TextField(blank=True)           # תיאור העבודה
    agreed_amount       = models.DecimalField(max_digits=12, decimal_places=2, default=0)   # סכום מוסכם
    withholding_tax_rate= models.DecimalField(max_digits=5, decimal_places=2, default=0)    # ניכוי מס במקור %
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date          = models.DateField(null=True, blank=True)
    end_date            = models.DateField(null=True, blank=True)
    contract_file = models.FileField(upload_to='freelancer_contracts/%Y/%m/', null=True, blank=True)
    contract_file_url = models.URLField(max_length=500, blank=True, default='')
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')
    notes               = models.TextField(blank=True, default='')
    created_at          = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'freelancer_agreements_dev'
        unique_together = ('freelancer', 'project')
        ordering        = ['-created_at']

    @property
    def total_paid(self):
        return sum(p.net_amount for p in self.payments.filter(status='paid'))

    @property
    def balance_due(self):
        return float(self.agreed_amount) - float(self.total_paid)

    def __str__(self):
        return f"{self.freelancer.full_name} - {self.project.name}"


# ── Freelancer Payment ─────────────────────────────────────────────────────

class FreelancerPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'ממתין'), ('paid', 'שולם'), ('cancelled', 'בוטל'),
    ]

    freelancer             = models.ForeignKey(Freelancer, on_delete=models.CASCADE, related_name='payments')
    agreement              = models.ForeignKey(FreelancerAgreement, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    project                = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='freelancer_payments')
    description            = models.TextField(blank=True, default='')
    amount                 = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date           = models.DateField(null=True, blank=True)
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    withholding_tax_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    withholding_tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    invoice_file = models.FileField(upload_to='freelancer_invoices/%Y/%m/', null=True, blank=True)
    invoice_file_url = models.URLField(max_length=500, blank=True, default='')
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')
    notes                  = models.TextField(blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'freelancer_payments_dev'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.withholding_tax_amount = round(float(self.amount) * float(self.withholding_tax_rate) / 100, 2)
        self.net_amount = round(float(self.amount) - float(self.withholding_tax_amount), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.freelancer.full_name} - ₪{self.amount}"


# ── Project Work Log ───────────────────────────────────────────────────────

class ProjectWorkLog(models.Model):
    """Daily work log entries for a project."""
    project     = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='work_logs')
    log_date    = models.DateField()
    title       = models.CharField(max_length=200, blank=True)
    content     = models.TextField(blank=True, default='')
    weather     = models.CharField(max_length=50, blank=True, default='')   # optional: sunny, rainy, etc.
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'project_work_logs_dev'
        ordering        = ['-log_date']
        unique_together = ('project', 'log_date')

    def __str__(self):
        return f"{self.project.name} - {self.log_date}"


# ── Project Site Photo ─────────────────────────────────────────────────────

class ProjectSitePhoto(models.Model):
    """Photos uploaded from the job site."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='site_photos')
    # Legacy local storage
    photo = models.ImageField(upload_to='site_photos/%Y/%m/', null=True, blank=True)
    # Cloudinary
    photo_url = models.URLField(max_length=500, blank=True, default='')
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')
    caption = models.CharField(max_length=255, blank=True)
    taken_by    = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True)
    taken_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_site_photos_dev'
        ordering = ['-taken_at']

    def __str__(self):
        return f"{self.project.name} - {self.taken_at.date()}"


# ── Add this to core/models.py ────────────────────────────────────────────────

class ShiftCorrection(models.Model):
    STATUS_CHOICES = [
        ('pending',  'ממתין לאישור'),
        ('approved', 'אושר'),
        ('rejected', 'נדחה'),
    ]

    worker      = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='corrections')
    date        = models.DateField()
    clock_in    = models.TimeField(null=True, blank=True)
    clock_out   = models.TimeField(null=True, blank=True)
    reason      = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    manager_note= models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_corrections'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shift_corrections_dev'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.worker.full_name} - {self.date} ({self.status})"


# ── Payroll Tax Brackets & Settings ────────────────────────────────────────
#
# Israeli payroll math (income tax brackets, BL/health rates, credit point
# value, etc.) is now stored in the database instead of hardcoded constants.
# This lets the owner update the law-defined numbers without a code release.
#
# Two tables:
#   payroll_tax_brackets_dev — list of brackets in order (1-7 typically)
#   payroll_settings_dev     — key/value pairs for everything else
#
# The engine reads these once per calculation (cached in-memory for 60s)
# and falls back to hardcoded 2026 defaults if either table is empty.

class PayrollTaxBracket(models.Model):
    """
    A single Israeli income-tax bracket.

    Brackets are evaluated in order of `bracket_index`. The last bracket
    (highest income) should have ceiling=NULL, meaning "no upper limit".
    """
    bracket_index = models.IntegerField(unique=True)
    ceiling       = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text='Monthly income ceiling in ₪. Leave blank for the top bracket (no limit).'
    )
    rate          = models.DecimalField(
        max_digits=6, decimal_places=4,
        help_text='Tax rate as decimal: 0.20 means 20%. 0.50 for top bracket includes mas yesef.'
    )
    notes         = models.CharField(max_length=200, blank=True, default='')
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_tax_brackets_dev'
        ordering = ['bracket_index']
        verbose_name = 'מדרגת מס'
        verbose_name_plural = 'מדרגות מס'

    def __str__(self):
        ceiling_str = f'≤ ₪{self.ceiling:,.0f}' if self.ceiling else 'מעל לכל המדרגות'
        return f'מדרגה {self.bracket_index}: {ceiling_str} → {float(self.rate)*100:g}%'


class PayrollSetting(models.Model):
    """
    Key/value table for non-bracket payroll settings:
      - tax_credit_point_value
      - bl_threshold, bl_upper_ceiling
      - bl_employee_low, bl_employee_high, bl_employer_low, bl_employer_high
      - health_threshold, health_employee_low, health_employee_high
      - default_pension_employee, default_pension_employer
      - default_severance, default_study_employee, default_study_employer

    Values are stored as DECIMAL — rates are decimals (0.0104 = 1.04%),
    thresholds and amounts are in ₪.
    """
    setting_key   = models.CharField(max_length=50, unique=True, primary_key=True)
    setting_value = models.DecimalField(max_digits=15, decimal_places=6)
    notes         = models.CharField(max_length=200, blank=True, default='')
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_settings_dev'
        ordering = ['setting_key']
        verbose_name = 'הגדרת שכר'
        verbose_name_plural = 'הגדרות שכר'

    def __str__(self):
        return f'{self.setting_key} = {self.setting_value}'


# ─── Freelancer Document ──────────────────────────────────────────────────

class FreelancerDocument(models.Model):
    """
    Personal documents for a קבלן משנה — applies to him as a person, not to
    a specific project. Examples: tax exemption certificate (אישור פטור
    מניכוי מס), ID copy, professional license, insurance, עוסק certificate.

    Project-scoped docs (signed contracts, payment invoices) live on the
    FreelancerAgreement / FreelancerPayment rows; this table is for things
    that don't tie to a single project.
    """
    DOC_TYPE_CHOICES = [
        ('tax_certificate',   'אישור ניכוי מס במקור'),
        ('tax_exemption',     'אישור פטור מניכוי מס'),
        ('osek_certificate',  'אישור עוסק מורשה'),
        ('id_copy',           'צילום תעודת זהות'),
        ('insurance',         'ביטוח חבות מקצועית'),
        ('license',           'רישיון מקצועי'),
        ('bank_confirmation', 'אישור ניהול חשבון בנק'),
        ('other',             'אחר'),
    ]

    freelancer           = models.ForeignKey(
        Freelancer, on_delete=models.CASCADE, related_name='documents'
    )
    doc_type             = models.CharField(
        max_length=30, choices=DOC_TYPE_CHOICES, default='other'
    )
    name                 = models.CharField(max_length=255)
    description          = models.TextField(blank=True, default='')
    # Cloudinary
    file_url             = models.URLField(max_length=500, blank=True, default='')
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')
    # Optional: tax exemption certs are valid for a calendar year
    valid_until          = models.DateField(null=True, blank=True)
    uploaded_by          = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_freelancer_docs',
    )
    uploaded_at          = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'freelancer_documents_dev'
        ordering     = ['-uploaded_at']
        verbose_name = 'מסמך קבלן משנה'

    def __str__(self):
        return f'{self.freelancer.full_name} — {self.name}'