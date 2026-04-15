from rest_framework import serializers
from .models import (User, Company, Worker, WorkerChild, Form101, Form106,
                     Project, ProjectFile, AttendanceRecord, PayrollRecord,
                     MaterialInvoice, Freelancer, FreelancerPayment,
                     ProjectWorkLog, ProjectSitePhoto)


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'id_number', 'phone', 'full_name', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = User
        fields = ['id_number', 'phone', 'full_name', 'password']

    def create(self, validated_data):
        return User.objects.create_user(
            id_number = validated_data['id_number'],
            password  = validated_data['password'],
            phone     = validated_data.get('phone', ''),
            full_name = validated_data['full_name'],
            role      = 'worker',
        )

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)


class SetPinSerializer(serializers.Serializer):
    pin = serializers.CharField(min_length=4, max_length=6)


# ══════════════════════════════════════════════════════════════════════════════
# COMPANY
# ══════════════════════════════════════════════════════════════════════════════

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Company
        fields = ['id', 'name', 'registration_code', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


# ══════════════════════════════════════════════════════════════════════════════
# WORKER
# ══════════════════════════════════════════════════════════════════════════════

class WorkerChildSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WorkerChild
        fields = ['id', 'name', 'birth_date']


class WorkerSerializer(serializers.ModelSerializer):
    children  = WorkerChildSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model  = Worker
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class WorkerListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model  = Worker
        fields = ['id', 'full_name', 'first_name', 'last_name', 'id_number',
                  'phone', 'position', 'wage_type', 'hourly_rate',
                  'monthly_salary', 'is_active', 'start_date']


class WorkerCreateSerializer(serializers.ModelSerializer):
    children = WorkerChildSerializer(many=True, required=False)

    class Meta:
        model  = Worker
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        children_data = validated_data.pop('children', [])
        worker = Worker.objects.create(**validated_data)
        for child in children_data:
            WorkerChild.objects.create(worker=worker, **child)
        return worker

    def update(self, instance, validated_data):
        children_data = validated_data.pop('children', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if children_data is not None:
            instance.children.all().delete()
            for child in children_data:
                WorkerChild.objects.create(worker=instance, **child)
        return instance


class WorkerMobileSerializer(serializers.ModelSerializer):
    """Lightweight worker profile returned to the mobile app after login."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model  = Worker
        fields = [
            'id', 'full_name', 'first_name', 'last_name',
            'id_number', 'phone', 'position', 'department',
            'wage_type', 'hourly_rate', 'monthly_salary',
            'is_active', 'start_date',
        ]
        read_only_fields = ['id']


# ══════════════════════════════════════════════════════════════════════════════
# FORMS 101 / 106
# ══════════════════════════════════════════════════════════════════════════════

class Form101Serializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)

    class Meta:
        model  = Form101
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class Form106Serializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)

    class Meta:
        model  = Form106
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT
# ══════════════════════════════════════════════════════════════════════════════

class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProjectFile
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at']


class ProjectSerializer(serializers.ModelSerializer):
    files        = ProjectFileSerializer(many=True, read_only=True)
    worker_count = serializers.SerializerMethodField()

    class Meta:
        model  = Project
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_worker_count(self, obj):
        return obj.workers.count()


class ProjectListSerializer(serializers.ModelSerializer):
    worker_count = serializers.SerializerMethodField()

    class Meta:
        model  = Project
        fields = ['id', 'name', 'client_name', 'status', 'site_address',
                  'start_date', 'end_date', 'worker_count', 'site_lat', 'site_lng']

    def get_worker_count(self, obj):
        return obj.workers.count()


class ProjectWorkerSerializer(serializers.ModelSerializer):
    """Project as seen by a worker in the mobile app — no financial data."""
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


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT WORK LOG & SITE PHOTO
# ══════════════════════════════════════════════════════════════════════════════

class ProjectWorkLogSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True, default='')

    class Meta:
        model  = ProjectWorkLog
        fields = [
            'id', 'project', 'log_date', 'title', 'content',
            'weather', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectSitePhotoSerializer(serializers.ModelSerializer):
    taken_by_name = serializers.CharField(
        source='taken_by.full_name', read_only=True, default='')

    class Meta:
        model  = ProjectSitePhoto
        fields = ['id', 'project', 'photo', 'caption', 'taken_by_name', 'taken_at']
        read_only_fields = ['id', 'taken_at']


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceSerializer(serializers.ModelSerializer):
    worker_name  = serializers.CharField(source='worker.full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = AttendanceRecord
        fields = '__all__'
        read_only_fields = ['id', 'hours_worked', 'overtime_hours', 'created_at']


class MyAttendanceSerializer(serializers.ModelSerializer):
    """Attendance shaped for the mobile Logs screen — flattened time strings."""
    project_name  = serializers.CharField(source='project.name', read_only=True, default='')
    date          = serializers.SerializerMethodField()
    clock_in_str  = serializers.SerializerMethodField()
    clock_out_str = serializers.SerializerMethodField()
    location      = serializers.SerializerMethodField()

    class Meta:
        model  = AttendanceRecord
        fields = [
            'id', 'date', 'clock_in_str', 'clock_out_str',
            'hours_worked', 'overtime_hours',
            'clock_in_lat', 'clock_in_lng',
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


class ClockInSerializer(serializers.Serializer):
    worker_id  = serializers.IntegerField()
    project_id = serializers.IntegerField(required=False, allow_null=True)
    latitude   = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude  = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    notes      = serializers.CharField(required=False, allow_blank=True)


class ClockOutSerializer(serializers.Serializer):
    latitude  = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    notes     = serializers.CharField(required=False, allow_blank=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAYROLL
# ══════════════════════════════════════════════════════════════════════════════

class PayrollRecordSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)

    class Meta:
        model  = PayrollRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayslipMobileSerializer(serializers.ModelSerializer):
    """PayrollRecord shaped for the mobile Summary screen."""
    label       = serializers.SerializerMethodField()
    net_label   = serializers.SerializerMethodField()
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


class PayrollCalculateSerializer(serializers.Serializer):
    worker_id = serializers.IntegerField()
    month     = serializers.IntegerField(min_value=1, max_value=12)
    year      = serializers.IntegerField(min_value=2000)
    save      = serializers.BooleanField(default=False)


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ══════════════════════════════════════════════════════════════════════════════

class MaterialInvoiceSerializer(serializers.ModelSerializer):
    worker_name  = serializers.CharField(source='worker.full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = MaterialInvoice
        fields = '__all__'
        read_only_fields = ['id', 'submitted_at', 'reviewed_at']


class InvoiceReviewSerializer(serializers.Serializer):
    status        = serializers.ChoiceField(choices=['approved', 'rejected'])
    manager_notes = serializers.CharField(required=False, allow_blank=True)


# ══════════════════════════════════════════════════════════════════════════════
# FREELANCER
# ══════════════════════════════════════════════════════════════════════════════

class FreelancerPaymentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model  = FreelancerPayment
        fields = '__all__'
        read_only_fields = ['id', 'withholding_tax_amount', 'net_amount', 'created_at']


class FreelancerSerializer(serializers.ModelSerializer):
    payments   = FreelancerPaymentSerializer(many=True, read_only=True)
    total_paid = serializers.SerializerMethodField()

    class Meta:
        model  = Freelancer
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_total_paid(self, obj):
        return float(sum(p.net_amount for p in obj.payments.filter(status='paid')))


class FreelancerListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Freelancer
        fields = ['id', 'full_name', 'id_number', 'phone', 'specialty', 'is_active']