import math
from datetime import date
from django.utils import timezone
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum, Count

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (User, Company, Worker, WorkerChild, Form101, Form106,
                     Project, ProjectFile, ProjectWorkLog, ProjectSitePhoto,
                     AttendanceRecord, PayrollRecord,
                     MaterialInvoice, Freelancer, FreelancerPayment,ShiftCorrection)
from .serializers import (
    UserSerializer, RegisterSerializer, ChangePasswordSerializer, SetPinSerializer,
    CompanySerializer,
    WorkerSerializer, WorkerListSerializer, WorkerCreateSerializer,
    WorkerChildSerializer, WorkerMobileSerializer,
    Form101Serializer, Form106Serializer,
    ProjectSerializer, ProjectListSerializer, ProjectFileSerializer,
    ProjectWorkerSerializer, ProjectWorkLogSerializer, ProjectSitePhotoSerializer,
    AttendanceSerializer, MyAttendanceSerializer, ClockInSerializer, ClockOutSerializer,
    PayrollRecordSerializer, PayslipMobileSerializer, PayrollCalculateSerializer,
    MaterialInvoiceSerializer, InvoiceReviewSerializer,
    FreelancerSerializer, FreelancerListSerializer, FreelancerPaymentSerializer,
)
from .permissions import IsManager, IsWorkerOrManager
from .engine import calculate_full_salary


# ── Helpers ────────────────────────────────────────────────────────────────────

def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'user':    UserSerializer(user).data,
    }


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a  = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_worker(user):
    """Return the Worker profile linked to a User, or None."""
    if hasattr(user, 'worker_profile') and user.worker_profile:
        return user.worker_profile
    return None


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("LOGIN ATTEMPT:", request.data)
        id_number = request.data.get('id_number')
        password  = request.data.get('password')
        try:
            user = User.objects.get(id_number=id_number, is_active=True)
            print(f"Found user: {user}, password ok: {user.check_password(password)}")
        except User.DoesNotExist:
            print("User not found")
            return Response({'error': 'מספר זהות או סיסמה שגויים'}, status=401)
        if not user.check_password(password):
            return Response({'error': 'מספר זהות או סיסמה שגויים'}, status=401)
        return Response(_issue_tokens(user))


# ── Replace RegisterView in views.py ─────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        user = serializer.save()
        id_number = user.id_number

        # Check if a worker already exists with this ID number
        try:
            worker = Worker.objects.get(id_number=id_number)
            # Link existing worker to this user
            if worker.user is None:
                worker.user = user
                worker.save(update_fields=['user'])
            needs_profile = False
        except Worker.DoesNotExist:
            # Create minimal worker profile
            Worker.objects.create(
                user           = user,
                id_number      = id_number,
                first_name     = user.full_name.split()[0],
                last_name      = ' '.join(user.full_name.split()[1:]) or '',
                phone          = user.phone,
                gender         = 'זכר',
                marital_status = 'רווק',
                start_date     = date.today(),
                wage_type      = 'hourly',
                hourly_rate    = 0,
                daily_rate     = 0,
                monthly_salary = 0,
            )
            needs_profile = True

        tokens = _issue_tokens(user)
        tokens['needs_profile'] = needs_profile
        return Response(tokens, status=201)



class CompleteProfileView(APIView):
    """Worker submits full profile after registration."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'Worker profile not found'}, status=404)

        data = request.data

        # Personal
        if data.get('first_name'):     worker.first_name     = data['first_name']
        if data.get('last_name'):      worker.last_name      = data['last_name']
        if data.get('gender'):         worker.gender         = data['gender']
        if data.get('birth_date'):     worker.birth_date     = data['birth_date']
        if data.get('marital_status'): worker.marital_status = data['marital_status']

        # Contact
        if data.get('phone'):          worker.phone          = data['phone']
        if data.get('email'):          worker.email          = data['email']
        if data.get('address'):        worker.address        = data['address']
        if data.get('city'):           worker.city           = data['city']

        # Employment
        if data.get('position'):       worker.position       = data['position']
        if data.get('start_date'):     worker.start_date     = data['start_date']

        # Bank
        if data.get('bank_name'):      worker.bank_name      = data['bank_name']
        if data.get('bank_branch'):    worker.bank_branch    = data['bank_branch']
        if data.get('bank_account'):   worker.bank_account   = data['bank_account']

        worker.save()

        # Handle children
        children = data.get('children', [])
        if children:
            worker.children.all().delete()
            for child in children:
                WorkerChild.objects.create(
                    worker     = worker,
                    name       = child.get('name', ''),
                    id_number  = child.get('id_number', ''),
                    birth_date = child.get('birth_date'),
                    gender     = child.get('gender', 'זכר'),
                )

        return Response({
            'message': 'פרופיל עודכן בהצלחה',
            'worker':  WorkerMobileSerializer(worker).data,
        })

# ── Add CompleteProfileView to views.py ───────────────────────────────────────

class CompleteProfileView(APIView):
    """Worker submits full profile after registration."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'Worker profile not found'}, status=404)

        data = request.data

        # Personal
        if data.get('first_name'):   worker.first_name     = data['first_name']
        if data.get('last_name'):    worker.last_name      = data['last_name']
        if data.get('gender'):       worker.gender         = data['gender']
        if data.get('birth_date'):   worker.birth_date     = data['birth_date']
        if data.get('marital_status'): worker.marital_status = data['marital_status']

        # Contact
        if data.get('phone'):        worker.phone          = data['phone']
        if data.get('email'):        worker.email          = data['email']
        if data.get('address'):      worker.address        = data['address']
        if data.get('city'):         worker.city           = data['city']

        # Employment
        if data.get('position'):     worker.position       = data['position']
        if data.get('start_date'):   worker.start_date     = data['start_date']

        # Bank
        if data.get('bank_name'):    worker.bank_name      = data['bank_name']
        if data.get('bank_branch'):  worker.bank_branch    = data['bank_branch']
        if data.get('bank_account'): worker.bank_account   = data['bank_account']

        worker.save()

        # Handle children
        children = data.get('children', [])
        if children:
            worker.children.all().delete()
            for child in children:
                WorkerChild.objects.create(
                    worker     = worker,
                    name       = child.get('name', ''),
                    id_number  = child.get('id_number', ''),
                    birth_date = child.get('birth_date'),
                    gender     = child.get('gender', 'זכר'),
                )

        return Response({
            'message': 'פרופיל עודכן בהצלחה',
            'worker':  WorkerMobileSerializer(worker).data,
        })

class PinLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_number = request.data.get('id_number')
        pin       = request.data.get('pin')
        if not id_number or not pin:
            return Response({'error': 'נדרש מספר זהות ו-PIN'}, status=400)
        try:
            user = User.objects.get(id_number=id_number, is_active=True)
        except User.DoesNotExist:
            return Response({'error': 'משתמש לא נמצא'}, status=404)
        if not user.pin_code or not check_password(pin, user.pin_code):
            return Response({'error': 'PIN שגוי'}, status=401)
        return Response(_issue_tokens(user))


class SetPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SetPinSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        request.user.pin_code = make_password(serializer.validated_data['pin'])
        request.user.save()
        return Response({'message': 'PIN הוגדר בהצלחה'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        if not request.user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'סיסמה ישנה שגויה'}, status=400)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'message': 'הסיסמה שונתה בהצלחה'})


class WorkerProfileView(APIView):
    """
    GET /api/auth/worker-profile/
    Returns the Worker record linked to the logged-in user.
    Called by the mobile app immediately after login to get Worker.id.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'לא נמצא פרופיל עובד עבור משתמש זה'}, status=404)
        return Response(WorkerMobileSerializer(worker).data)


# ══════════════════════════════════════════════════════════════════════════════
# WORKERS
# ══════════════════════════════════════════════════════════════════════════════

class WorkerListCreateView(generics.ListCreateAPIView):
    search_fields   = ['first_name', 'last_name', 'id_number', 'phone']
    ordering_fields = ['first_name', 'last_name', 'start_date']

    def get_queryset(self):
        return Worker.objects.all().prefetch_related('children').order_by('first_name', 'last_name')

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsManager()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WorkerCreateSerializer
        return WorkerListSerializer


class WorkerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = Worker.objects.all().prefetch_related('children')
    permission_classes = [IsAuthenticated, IsManager]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return WorkerCreateSerializer
        return WorkerSerializer

    def destroy(self, request, *args, **kwargs):
        worker = self.get_object()
        worker.is_active = False
        worker.save()
        return Response({'message': 'העובד הושבת'})


class WorkerChildrenView(generics.ListCreateAPIView):
    serializer_class   = WorkerChildSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        return WorkerChild.objects.filter(worker_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        serializer.save(worker_id=self.kwargs['pk'])


class RecalcTaxPointsView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            worker = Worker.objects.prefetch_related('children').get(id=pk)
        except Worker.DoesNotExist:
            return Response({'error': 'עובד לא נמצא'}, status=404)
        worker.tax_points = worker.calculate_tax_points()
        worker.save()
        return Response({'tax_points': worker.tax_points})


# ── Forms ──────────────────────────────────────────────────────────────────────

class Form101View(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            form = Form101.objects.get(worker_id=pk)
            return Response(Form101Serializer(form).data)
        except Form101.DoesNotExist:
            return Response({'error': 'טופס 101 לא נמצא'}, status=404)

    def post(self, request, pk):
        try:
            worker = Worker.objects.get(id=pk)
        except Worker.DoesNotExist:
            return Response({'error': 'עובד לא נמצא'}, status=404)
        form, _ = Form101.objects.get_or_create(worker=worker)
        s = Form101Serializer(form, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            worker.tax_points = worker.calculate_tax_points()
            worker.save()
            return Response(s.data)
        return Response(s.errors, status=400)


class Form106ListView(generics.ListCreateAPIView):
    serializer_class   = Form106Serializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        return Form106.objects.filter(worker_id=self.kwargs['pk']).order_by('-tax_year')

    def perform_create(self, serializer):
        serializer.save(worker_id=self.kwargs['pk'])


class Form106DetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = Form106.objects.all()
    serializer_class   = Form106Serializer
    permission_classes = [IsAuthenticated, IsManager]


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

class ProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        qs = Project.objects.prefetch_related('workers', 'files').order_by('-created_at')
        s  = self.request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)
        return qs

    def get_serializer_class(self):
        return ProjectListSerializer if self.request.method == 'GET' else ProjectSerializer


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = Project.objects.prefetch_related('workers', 'files')
    serializer_class   = ProjectSerializer
    permission_classes = [IsAuthenticated, IsManager]


class ProjectAssignWorkersView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            project = Project.objects.get(id=pk)
        except Project.DoesNotExist:
            return Response({'error': 'פרויקט לא נמצא'}, status=404)
        project.workers.set(request.data.get('worker_ids', []))
        return Response({'message': 'עובדים עודכנו'})


class ProjectFileView(generics.ListCreateAPIView):
    serializer_class   = ProjectFileSerializer
    permission_classes = [IsAuthenticated, IsManager]
    parser_classes     = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ProjectFile.objects.filter(project_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        project  = Project.objects.get(id=self.kwargs['pk'])
        file_obj = self.request.FILES.get('file')
        serializer.save(project=project, file_name=file_obj.name if file_obj else 'קובץ')


class ProjectFileDeleteView(generics.DestroyAPIView):
    queryset           = ProjectFile.objects.all()
    serializer_class   = ProjectFileSerializer
    permission_classes = [IsAuthenticated, IsManager]


class MyProjectsView(APIView):
    """
    GET /api/projects/my/
    Workers get only their assigned active projects.
    Managers get all active projects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_manager:
            projects = (
                Project.objects
                .prefetch_related('files', 'workers')
                .filter(status='active')
                .order_by('-created_at')
            )
        else:
            worker = _get_worker(request.user)
            if not worker:
                return Response([])
            projects = (
                worker.projects
                .prefetch_related('files', 'workers')
                .filter(status='active')
                .order_by('-created_at')
            )
        return Response(ProjectWorkerSerializer(projects, many=True).data)


class ProjectBlueprintsView(APIView):
    """
    GET /api/projects/<pk>/blueprints/
    Returns blueprint, map, and document files for the slide-down panel.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        files = (
            ProjectFile.objects
            .filter(project_id=pk, file_type__in=['blueprint', 'map', 'document'])
            .order_by('file_type', 'file_name')
        )
        return Response([
            {
                'id':          f.id,
                'name':        f.file_name,
                'type':        f.file_type,
                'description': f.description,
                'url':         request.build_absolute_uri(f.file.url) if f.file else '',
            }
            for f in files
        ])


class ProjectNotesView(APIView):
    """
    GET  /api/projects/<pk>/notes/  — today's + recent manager notes
    POST /api/projects/<pk>/notes/  — manager creates/updates a note (manager only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        today = date.today()
        logs  = (
            ProjectWorkLog.objects
            .filter(project_id=pk, log_date__gte=today)
            .select_related('created_by')
            .order_by('-log_date')
        )
        if not logs.exists():
            logs = (
                ProjectWorkLog.objects
                .filter(project_id=pk)
                .select_related('created_by')
                .order_by('-log_date')[:5]
            )
        return Response([
            {
                'id':      log.id,
                'author':  log.created_by.full_name if log.created_by else 'מנהל',
                'date':    log.log_date.strftime('%Y-%m-%d'),
                'title':   log.title,
                'text':    log.content,
                'weather': log.weather,
                'time':    log.created_at.strftime('%H:%M'),
            }
            for log in logs
        ])

    def post(self, request, pk):
        if not request.user.is_manager:
            return Response({'error': 'גישה מותרת למנהלים בלבד'}, status=403)
        try:
            project = Project.objects.get(id=pk)
        except Project.DoesNotExist:
            return Response({'error': 'פרויקט לא נמצא'}, status=404)

        log_date = request.data.get('log_date', date.today().isoformat())
        log, created = ProjectWorkLog.objects.get_or_create(
            project=project, log_date=log_date,
            defaults={'created_by': request.user},
        )
        log.title      = request.data.get('title', log.title)
        log.content    = request.data.get('content', log.content)
        log.weather    = request.data.get('weather', log.weather)
        log.created_by = request.user
        log.save()

        return Response({
            'id':      log.id,
            'author':  request.user.full_name,
            'date':    log.log_date.strftime('%Y-%m-%d'),
            'title':   log.title,
            'text':    log.content,
            'time':    log.created_at.strftime('%H:%M'),
        }, status=201 if created else 200)


class SitePhotoView(APIView):
    """
    GET  /api/projects/<pk>/photos/  — list site photos
    POST /api/projects/<pk>/photos/  — upload a new photo (multipart)
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request, pk):
        photos = ProjectSitePhoto.objects.filter(project_id=pk).order_by('-taken_at')
        return Response([
            {
                'id':       p.id,
                'url':      request.build_absolute_uri(p.photo.url),
                'caption':  p.caption,
                'taken_by': p.taken_by.full_name if p.taken_by else '',
                'taken_at': p.taken_at.isoformat(),
            }
            for p in photos
        ])

    def post(self, request, pk):
        try:
            project = Project.objects.get(id=pk)
        except Project.DoesNotExist:
            return Response({'error': 'פרויקט לא נמצא'}, status=404)

        photo_file = request.FILES.get('photo')
        if not photo_file:
            return Response({'error': 'לא נשלחה תמונה'}, status=400)

        worker = _get_worker(request.user)
        photo  = ProjectSitePhoto.objects.create(
            project  = project,
            photo    = photo_file,
            caption  = request.data.get('caption', ''),
            taken_by = worker,
        )
        return Response({
            'id':       photo.id,
            'url':      request.build_absolute_uri(photo.photo.url),
            'caption':  photo.caption,
            'taken_at': photo.taken_at.isoformat(),
        }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════

class ClockInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ClockInSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=400)
        data       = s.validated_data
        worker_id  = data['worker_id']
        project_id = data.get('project_id')
        lat, lng   = data.get('latitude'), data.get('longitude')

        try:
            worker = Worker.objects.get(id=worker_id, is_active=True)
        except Worker.DoesNotExist:
            return Response({'error': 'עובד לא נמצא'}, status=404)

        if AttendanceRecord.objects.filter(worker=worker, status='open').exists():
            return Response({'error': 'העובד כבר במשמרת פתוחה'}, status=400)

        if project_id and lat and lng:
            try:
                project = Project.objects.get(id=project_id)
                if project.site_lat and project.site_lng:
                    dist = haversine(lat, lng, project.site_lat, project.site_lng)
                    if dist > project.gps_radius_m:
                        return Response(
                            {'error': f'רחוק מדי מהאתר ({int(dist)} מטר)'},
                            status=400,
                        )
            except Project.DoesNotExist:
                pass

        record = AttendanceRecord.objects.create(
            worker=worker, project_id=project_id,
            clock_in=timezone.now(),
            clock_in_lat=lat, clock_in_lng=lng,
            notes=data.get('notes', ''), status='open',
        )
        return Response(
            {'message': f'כניסה נרשמה - {worker.full_name}', 'record_id': record.id},
            status=201,
        )


class ClockOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, record_id):
        s = ClockOutSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=400)
        try:
            record = AttendanceRecord.objects.get(id=record_id, status='open')
        except AttendanceRecord.DoesNotExist:
            return Response({'error': 'משמרת פתוחה לא נמצאה'}, status=404)
        data = s.validated_data
        record.clock_out     = timezone.now()
        record.clock_out_lat = data.get('latitude')
        record.clock_out_lng = data.get('longitude')
        record.notes         = data.get('notes', record.notes)
        record.status        = 'closed'
        record.save()
        return Response({
            'hours_worked':   float(record.hours_worked or 0),
            'overtime_hours': float(record.overtime_hours or 0),
        })


class AttendanceListView(generics.ListAPIView):
    serializer_class   = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        qs = AttendanceRecord.objects.select_related('worker', 'project').order_by('-clock_in')
        for param in ['worker_id', 'project_id']:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{param: val})
        month = self.request.query_params.get('month')
        year  = self.request.query_params.get('year')
        if month: qs = qs.filter(clock_in__month=month)
        if year:  qs = qs.filter(clock_in__year=year)
        return qs


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = AttendanceRecord.objects.all()
    serializer_class   = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsManager]


class OpenAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        records = AttendanceRecord.objects.filter(status='open').select_related('worker', 'project')
        return Response(AttendanceSerializer(records, many=True).data)


class MonthlySummaryView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        month = request.query_params.get('month', timezone.now().month)
        year  = request.query_params.get('year', timezone.now().year)
        rows  = (
            AttendanceRecord.objects
            .filter(clock_in__month=month, clock_in__year=year, status__in=['closed', 'approved'])
            .values('worker__id', 'worker__first_name', 'worker__last_name')
            .annotate(total_days=Count('id'), total_hours=Sum('hours_worked'), overtime=Sum('overtime_hours'))
        )
        return Response([{
            'worker_id':      r['worker__id'],
            'worker_name':    f"{r['worker__first_name']} {r['worker__last_name']}",
            'total_days':     r['total_days'],
            'total_hours':    float(r['total_hours'] or 0),
            'overtime_hours': float(r['overtime'] or 0),
        } for r in rows])


class MyAttendanceView(APIView):
    """
    GET /api/attendance/my/?month=&year=
    Worker sees only their own attendance logs.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)
        now   = timezone.now()
        month = int(request.query_params.get('month', now.month))
        year  = int(request.query_params.get('year', now.year))
        records = (
            AttendanceRecord.objects
            .filter(worker=worker, clock_in__month=month, clock_in__year=year)
            .select_related('project')
            .order_by('-clock_in')
        )
        return Response(MyAttendanceSerializer(records, many=True).data)


class MyMonthlySummaryView(APIView):
    """
    GET /api/attendance/my-summary/?month=&year=
    Returns total_days, total_hours, overtime + logs list in one call.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)
        now   = timezone.now()
        month = int(request.query_params.get('month', now.month))
        year  = int(request.query_params.get('year', now.year))
        records = (
            AttendanceRecord.objects
            .filter(
                worker=worker,
                clock_in__month=month,
                clock_in__year=year,
                status__in=['closed', 'approved'],
            )
            .select_related('project')
            .order_by('clock_in')
        )
        agg = records.aggregate(
            total_hours=Sum('hours_worked'),
            overtime=Sum('overtime_hours'),
        )
        return Response({
            'month':          month,
            'year':           year,
            'total_days':     records.count(),
            'total_hours':    float(agg['total_hours'] or 0),
            'overtime_hours': float(agg['overtime'] or 0),
            'logs':           MyAttendanceSerializer(records, many=True).data,
        })


class MyOpenAttendanceView(APIView):
    """
    GET /api/attendance/my-open/
    Checks if the worker is currently clocked in.
    Used on app startup to restore the timer.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'open': False, 'record': None})
        try:
            record = AttendanceRecord.objects.get(worker=worker, status='open')
            return Response({
                'open':       True,
                'record_id':  record.id,
                'clock_in':   record.clock_in.isoformat(),
                'project_id': record.project_id,
                'lat':        float(record.clock_in_lat) if record.clock_in_lat else None,
                'lng':        float(record.clock_in_lng) if record.clock_in_lng else None,
            })
        except AttendanceRecord.DoesNotExist:
            return Response({'open': False, 'record': None})
        except AttendanceRecord.MultipleObjectsReturned:
            record = AttendanceRecord.objects.filter(worker=worker, status='open').last()
            return Response({
                'open':      True,
                'record_id': record.id,
                'clock_in':  record.clock_in.isoformat(),
            })


# ══════════════════════════════════════════════════════════════════════════════
# PAYROLL
# ══════════════════════════════════════════════════════════════════════════════

class PayrollCalculateView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request):
        s = PayrollCalculateSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=400)
        data = s.validated_data
        try:
            worker = Worker.objects.get(id=data['worker_id'], is_active=True)
        except Worker.DoesNotExist:
            return Response({'error': 'עובד לא נמצא'}, status=404)

        agg = AttendanceRecord.objects.filter(
            worker=worker, clock_in__month=data['month'],
            clock_in__year=data['year'], status__in=['closed', 'approved'],
        ).aggregate(total_hours=Sum('hours_worked'), total_ot=Sum('overtime_hours'))

        total  = float(agg['total_hours'] or 0)
        ot     = float(agg['total_ot'] or 0)
        result = calculate_full_salary(
            {k: getattr(worker, k) for k in [
                'wage_type', 'hourly_rate', 'monthly_salary', 'tax_points',
                'travel_allowance', 'pension_rate_employee', 'pension_rate_employer',
                'severance_rate', 'study_fund_employee', 'study_fund_employer',
            ]},
            {'regular_hours': round(total - ot, 2), 'overtime_hours': ot}
        )

        if data['save']:
            PayrollRecord.objects.update_or_create(
                worker=worker, month=data['month'], year=data['year'],
                defaults={**result, 'regular_hours': round(total - ot, 2), 'overtime_hours': ot}
            )

        result['worker_name'] = worker.full_name
        result['month']       = data['month']
        result['year']        = data['year']
        return Response(result)


class PayrollListView(generics.ListAPIView):
    serializer_class   = PayrollRecordSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        qs = PayrollRecord.objects.select_related('worker').order_by('-year', '-month')
        for param in ['worker_id', 'month', 'year']:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{param: val})
        return qs


class PayrollDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = PayrollRecord.objects.all()
    serializer_class   = PayrollRecordSerializer
    permission_classes = [IsAuthenticated, IsManager]


class MyPayslipsView(APIView):
    """
    GET /api/payroll/my/?year=
    Worker's own payslips only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)
        qs = PayrollRecord.objects.filter(worker=worker).order_by('-year', '-month')
        year = request.query_params.get('year')
        if year:
            qs = qs.filter(year=year)
        return Response(PayslipMobileSerializer(qs, many=True).data)


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ══════════════════════════════════════════════════════════════════════════════

class InvoiceListCreateView(generics.ListCreateAPIView):
    serializer_class   = MaterialInvoiceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs   = MaterialInvoice.objects.select_related('worker', 'project').order_by('-submitted_at')
        user = self.request.user
        if user.is_worker and hasattr(user, 'worker_profile'):
            qs = qs.filter(worker=user.worker_profile)
        s = self.request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)
        return qs


class InvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = MaterialInvoice.objects.all()
    serializer_class   = MaterialInvoiceSerializer
    permission_classes = [IsAuthenticated]


class InvoiceReviewView(APIView):
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            invoice = MaterialInvoice.objects.get(id=pk)
        except MaterialInvoice.DoesNotExist:
            return Response({'error': 'חשבונית לא נמצאה'}, status=404)
        s = InvoiceReviewSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=400)
        invoice.status        = s.validated_data['status']
        invoice.manager_notes = s.validated_data.get('manager_notes', '')
        invoice.reviewed_at   = timezone.now()
        invoice.save()
        return Response({'message': 'הסטטוס עודכן'})


class MyInvoicesView(APIView):
    """
    GET  /api/invoices/my/  — worker's submitted invoices
    POST /api/invoices/my/  — worker submits a new invoice photo
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response([])
        qs = MaterialInvoice.objects.filter(worker=worker).order_by('-submitted_at')
        if status_filter := request.query_params.get('status'):
            qs = qs.filter(status=status_filter)
        return Response([
            {
                'id':            inv.id,
                'project':       inv.project.name if inv.project else '',
                'supplier_name': inv.supplier_name,
                'description':   inv.description,
                'amount':        float(inv.amount),
                'invoice_date':  inv.invoice_date.isoformat() if inv.invoice_date else '',
                'status':        inv.status,
                'manager_notes': inv.manager_notes,
                'image_url':     request.build_absolute_uri(inv.image.url) if inv.image else '',
                'submitted_at':  inv.submitted_at.isoformat() if inv.submitted_at else '',
            }
            for inv in qs
        ])

    def post(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)
        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'נדרשת תמונה של החשבונית'}, status=400)
        try:
            amount = float(request.data.get('amount', 0))
        except (ValueError, TypeError):
            return Response({'error': 'סכום לא תקין'}, status=400)
        try:
            inv_date = date.fromisoformat(request.data.get('invoice_date', date.today().isoformat()))
        except ValueError:
            inv_date = date.today()

        project = None
        if project_id := request.data.get('project'):
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                pass

        invoice = MaterialInvoice.objects.create(
            worker        = worker,
            project       = project,
            supplier_name = request.data.get('supplier_name', ''),
            description   = request.data.get('description', ''),
            amount        = amount,
            invoice_date  = inv_date,
            image         = image,
            status        = 'pending',
        )
        return Response({
            'id':           invoice.id,
            'status':       invoice.status,
            'amount':       float(invoice.amount),
            'submitted_at': invoice.submitted_at.isoformat(),
        }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

class MyDocumentsView(APIView):
    """
    GET /api/documents/my/
    Returns document-type project files for the worker's assigned projects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if request.user.is_manager:
            project_ids = list(Project.objects.values_list('id', flat=True))
        elif worker:
            project_ids = list(worker.projects.values_list('id', flat=True))
        else:
            return Response([])

        files = (
            ProjectFile.objects
            .filter(project_id__in=project_ids, file_type='document')
            .select_related('project')
            .order_by('-uploaded_at')
        )
        return Response([
            {
                'id':          f.id,
                'name':        f.file_name,
                'description': f.description,
                'project':     f.project.name,
                'date':        f.uploaded_at.strftime('%Y-%m-%d') if f.uploaded_at else '',
                'url':         request.build_absolute_uri(f.file.url) if f.file else '',
            }
            for f in files
        ])


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class DashboardView(APIView):
    """
    GET /api/dashboard/
    Manager overview: who's clocked in, pending invoices, today's totals.
    """
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        now   = timezone.now()
        today = now.date()

        open_records = (
            AttendanceRecord.objects
            .filter(status='open')
            .select_related('worker', 'project')
        )
        clocked_in = [
            {
                'worker_id':   r.worker.id,
                'worker_name': r.worker.full_name,
                'project':     r.project.name if r.project else '',
                'clock_in':    r.clock_in.strftime('%H:%M'),
                'record_id':   r.id,
            }
            for r in open_records
        ]

        today_agg = AttendanceRecord.objects.filter(
            clock_in__date=today, status__in=['closed', 'approved']
        ).aggregate(count=Count('id'), total_hours=Sum('hours_worked'))

        return Response({
            'clocked_in_now':   clocked_in,
            'clocked_in_count': len(clocked_in),
            'today_shifts':     today_agg['count'] or 0,
            'today_hours':      float(today_agg['total_hours'] or 0),
            'pending_invoices': MaterialInvoice.objects.filter(status='pending').count(),
            'active_workers':   Worker.objects.filter(is_active=True).count(),
            'active_projects':  Project.objects.filter(status='active').count(),
            'date':             today.isoformat(),
            'time':             now.strftime('%H:%M'),
        })


# ══════════════════════════════════════════════════════════════════════════════
# FREELANCERS
# ══════════════════════════════════════════════════════════════════════════════

class FreelancerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        return Freelancer.objects.prefetch_related('payments').order_by('full_name')

    def get_serializer_class(self):
        return FreelancerListSerializer if self.request.method == 'GET' else FreelancerSerializer


class FreelancerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = Freelancer.objects.prefetch_related('payments')
    serializer_class   = FreelancerSerializer
    permission_classes = [IsAuthenticated, IsManager]


class FreelancerPaymentListView(generics.ListCreateAPIView):
    serializer_class   = FreelancerPaymentSerializer
    permission_classes = [IsAuthenticated, IsManager]

    def get_queryset(self):
        return FreelancerPayment.objects.filter(freelancer_id=self.kwargs['pk']).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(freelancer_id=self.kwargs['pk'])


class FreelancerPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset           = FreelancerPayment.objects.all()
    serializer_class   = FreelancerPaymentSerializer
    permission_classes = [IsAuthenticated, IsManager]


# ── Add these views to core/views.py ─────────────────────────────────────────
from django.utils import timezone as tz

class ShiftCorrectionListCreateView(APIView):
    """
    GET  /api/corrections/my/      — worker sees their own corrections
    POST /api/corrections/my/      — worker submits a new correction
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)
        corrections = ShiftCorrection.objects.filter(worker=worker).order_by('-created_at')
        return Response([{
            'id':           c.id,
            'date':         c.date.strftime('%Y-%m-%d'),
            'clock_in':     c.clock_in.strftime('%H:%M') if c.clock_in else None,
            'clock_out':    c.clock_out.strftime('%H:%M') if c.clock_out else None,
            'reason':       c.reason,
            'status':       c.status,
            'manager_note': c.manager_note,
            'created_at':   c.created_at.strftime('%Y-%m-%d %H:%M'),
        } for c in corrections])

    def post(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response({'error': 'פרופיל עובד לא נמצא'}, status=404)

        date      = request.data.get('date')
        clock_in  = request.data.get('clock_in')
        clock_out = request.data.get('clock_out')
        reason    = request.data.get('reason', '').strip()

        if not date or not reason:
            return Response({'error': 'תאריך וסיבה הם שדות חובה'}, status=400)

        # Check if correction already pending for this date
        if ShiftCorrection.objects.filter(
            worker=worker, date=date, status='pending'
        ).exists():
            return Response({'error': 'כבר קיימת בקשת תיקון ממתינה לתאריך זה'}, status=400)

        correction = ShiftCorrection.objects.create(
            worker    = worker,
            date      = date,
            clock_in  = clock_in,
            clock_out = clock_out,
            reason    = reason,
        )
        return Response({
            'id':        correction.id,
            'date':      correction.date.strftime('%Y-%m-%d'),
            'status':    correction.status,
            'message':   'בקשת התיקון נשלחה בהצלחה',
        }, status=201)


class ShiftCorrectionManagerView(APIView):
    """
    GET  /api/corrections/          — manager sees all pending corrections
    POST /api/corrections/<id>/review/ — manager approves or rejects
    """
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        status_filter = request.query_params.get('status', 'pending')
        corrections = ShiftCorrection.objects.filter(
            status=status_filter
        ).select_related('worker').order_by('-created_at')
        return Response([{
            'id':           c.id,
            'worker_name':  c.worker.full_name,
            'worker_id':    c.worker.id,
            'date':         c.date.strftime('%Y-%m-%d'),
            'clock_in':     c.clock_in.strftime('%H:%M') if c.clock_in else None,
            'clock_out':    c.clock_out.strftime('%H:%M') if c.clock_out else None,
            'reason':       c.reason,
            'status':       c.status,
            'manager_note': c.manager_note,
            'created_at':   c.created_at.strftime('%Y-%m-%d %H:%M'),
        } for c in corrections])


class ShiftCorrectionReviewView(APIView):
    """
    POST /api/corrections/<id>/review/
    Body: { "status": "approved"/"rejected", "manager_note": "..." }
    """
    permission_classes = [IsAuthenticated, IsManager]

    def post(self, request, pk):
        try:
            correction = ShiftCorrection.objects.select_related('worker').get(id=pk)
        except ShiftCorrection.DoesNotExist:
            return Response({'error': 'בקשה לא נמצאה'}, status=404)

        new_status   = request.data.get('status')
        manager_note = request.data.get('manager_note', '')

        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'סטטוס לא תקין'}, status=400)

        correction.status       = new_status
        correction.manager_note = manager_note
        correction.reviewed_by  = request.user
        correction.reviewed_at  = tz.now()
        correction.save()

        # If approved — create or update AttendanceRecord
        if new_status == 'approved':
            from datetime import datetime, timedelta
            worker    = correction.worker
            date      = correction.date
            ci_time   = correction.clock_in
            co_time   = correction.clock_out

            # Build datetime objects
            clock_in_dt  = datetime.combine(date, ci_time)  if ci_time  else datetime.combine(date, datetime.min.time())
            clock_out_dt = datetime.combine(date, co_time)  if co_time  else None
            hours = 0
            if clock_in_dt and clock_out_dt:
                delta = clock_out_dt - clock_in_dt
                hours = round(delta.total_seconds() / 3600, 2)

            record, created = AttendanceRecord.objects.get_or_create(
                worker   = worker,
                clock_in__date = date,
                defaults = {
                    'clock_in':    clock_in_dt,
                    'clock_out':   clock_out_dt,
                    'hours_worked': hours,
                    'status':      'approved',
                    'notes':       f'תיקון ידני: {correction.reason}',
                }
            )
            if not created:
                # Update existing
                if ci_time:  record.clock_in  = clock_in_dt
                if co_time:  record.clock_out = clock_out_dt
                if hours:    record.hours_worked = hours
                record.status = 'approved'
                record.notes  = f'תיקון ידני: {correction.reason}'
                record.save()

        return Response({
            'message': 'הבקשה עודכנה בהצלחה',
            'status':  correction.status,
        })