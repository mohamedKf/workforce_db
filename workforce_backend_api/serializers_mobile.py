# ─────────────────────────────────────────────────────────────────────────────
# ADD THESE TO YOUR EXISTING serializers.py
# (paste at the bottom, after FreelancerListSerializer)
# ─────────────────────────────────────────────────────────────────────────────

from .models import ProjectWorkLog, ProjectSitePhoto


# ── Worker self-view (what the mobile app gets after login) ──────────────────

class WorkerMobileSerializer(serializers.ModelSerializer):
    """
    Lightweight worker profile for the mobile app.
    Returned after login so the app knows the Worker.id and basic info.
    """
    full_name   = serializers.CharField(read_only=True)
    hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model  = Worker
        fields = [
            'id', 'full_name', 'first_name', 'last_name',
            'id_number', 'phone', 'position', 'department',
            'wage_type', 'hourly_rate', 'monthly_salary',
            'is_active', 'start_date',
        ]
        read_only_fields = ['id']


# ── My attendance (worker sees only their own) ────────────────────────────────

class MyAttendanceSerializer(serializers.ModelSerializer):
    """
    Attendance record shaped for the mobile Logs screen.
    Returns flattened time strings and location string.
    """
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    date         = serializers.SerializerMethodField()
    clock_in_str = serializers.SerializerMethodField()
    clock_out_str= serializers.SerializerMethodField()
    location     = serializers.SerializerMethodField()

    class Meta:
        model  = AttendanceRecord
        fields = [
            'id', 'date', 'clock_in_str', 'clock_out_str',
            'hours_worked', 'overtime_hours',
            'clock_in_lat', 'clock_in_lng',
            'clock_out_lat', 'clock_out_lng',
            'location', 'status', 'notes', 'project_name',
        ]

    def get_date(self, obj):
        return obj.clock_in.strftime('%Y-%m-%d') if obj.clock_in else ''

    def get_clock_in_str(self, obj):
        return obj.clock_in.strftime('%H:%M') if obj.clock_in else '--:--'

    def get_clock_out_str(self, obj):
        return obj.clock_out.strftime('%H:%M') if obj.clock_out else '--:--'

    def get_location(self, obj):
        if obj.clock_in_lat and obj.clock_in_lng:
            return f"{float(obj.clock_in_lat):.5f}, {float(obj.clock_in_lng):.5f}"
        return ''


# ── Project (worker view — no budget/cost info) ───────────────────────────────

class ProjectWorkerSerializer(serializers.ModelSerializer):
    """
    Project as seen by a worker in the mobile app.
    Includes GPS, address, file counts — excludes financial data.
    """
    blueprint_count = serializers.SerializerMethodField()
    worker_count    = serializers.SerializerMethodField()

    class Meta:
        model  = Project
        fields = [
            'id', 'name', 'client_name', 'status',
            'site_address', 'site_lat', 'site_lng', 'gps_radius_m',
            'start_date', 'end_date',
            'notes', 'blueprint_count', 'worker_count',
        ]

    def get_blueprint_count(self, obj):
        return obj.files.filter(file_type__in=['blueprint', 'map', 'document']).count()

    def get_worker_count(self, obj):
        return obj.workers.count()


# ── Project Work Log ──────────────────────────────────────────────────────────

class ProjectWorkLogSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')

    class Meta:
        model  = ProjectWorkLog
        fields = [
            'id', 'project', 'log_date', 'title', 'content',
            'weather', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ── Site Photo ────────────────────────────────────────────────────────────────

class ProjectSitePhotoSerializer(serializers.ModelSerializer):
    taken_by_name = serializers.CharField(source='taken_by.full_name', read_only=True, default='')

    class Meta:
        model  = ProjectSitePhoto
        fields = ['id', 'project', 'photo', 'caption', 'taken_by_name', 'taken_at']
        read_only_fields = ['id', 'taken_at']


class SitePhotoUploadSerializer(serializers.Serializer):
    project_id  = serializers.IntegerField()
    photo       = serializers.ImageField()
    caption     = serializers.CharField(required=False, allow_blank=True, default='')


# ── Monthly summary for a single worker ──────────────────────────────────────

class WorkerMonthlySummarySerializer(serializers.Serializer):
    """Returned by GET /api/attendance/my-summary/?month=&year="""
    month        = serializers.IntegerField()
    year         = serializers.IntegerField()
    total_days   = serializers.IntegerField()
    total_hours  = serializers.FloatField()
    overtime_hours = serializers.FloatField()
    logs         = MyAttendanceSerializer(many=True)


# ── Payslip (mobile summary screen) ──────────────────────────────────────────

class PayslipMobileSerializer(serializers.ModelSerializer):
    """PayrollRecord shaped for the mobile Summary screen."""
    label      = serializers.SerializerMethodField()
    net_label  = serializers.SerializerMethodField()
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)

    class Meta:
        model  = PayrollRecord
        fields = [
            'id', 'month', 'year', 'label', 'net_label',
            'gross_salary', 'net_salary', 'total_deductions',
            'income_tax', 'bituah_leumi', 'health_insurance',
            'pension_employee', 'study_fund_employee',
            'regular_hours', 'overtime_hours',
            'status', 'worker_name',
        ]

    def get_label(self, obj):
        months_he = [
            '', 'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
            'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר',
        ]
        return f"תלוש שכר — {months_he[obj.month]} {obj.year}"

    def get_net_label(self, obj):
        return f"₪{float(obj.net_salary):,.0f} נטו"
