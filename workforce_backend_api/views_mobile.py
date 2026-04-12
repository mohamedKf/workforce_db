# ─────────────────────────────────────────────────────────────────────────────
# views_mobile.py
#
# All new views for the KivyMD mobile app.
# Add these to your views.py (or keep in a separate file and include in urls.py)
# ─────────────────────────────────────────────────────────────────────────────

import math
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import datetime, date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import (
    Worker, Project, ProjectFile, ProjectWorkLog, ProjectSitePhoto,
    AttendanceRecord, PayrollRecord, MaterialInvoice,
)
from .permissions import IsManager, IsWorkerOrManager
from .serializers_mobile import (
    WorkerMobileSerializer,
    MyAttendanceSerializer,
    WorkerMonthlySummarySerializer,
    ProjectWorkerSerializer,
    ProjectWorkLogSerializer,
    ProjectSitePhotoSerializer,
    SitePhotoUploadSerializer,
    PayslipMobileSerializer,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_worker(user) -> Worker | None:
    """Return the Worker linked to a User, or None."""
    if hasattr(user, 'worker_profile') and user.worker_profile:
        return user.worker_profile
    return None


# ══════════════════════════════════════════════════════════════════════════════
# AUTH EXTRAS
# ══════════════════════════════════════════════════════════════════════════════

class WorkerProfileView(APIView):
    """
    GET /api/auth/worker-profile/
    Returns the Worker record linked to the logged-in user.
    Called by the mobile app right after login to get Worker.id.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response(
                {'error': 'לא נמצא פרופיל עובד עבור משתמש זה'},
                status=404,
            )
        return Response(WorkerMobileSerializer(worker).data)


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE — WORKER SELF-SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class MyAttendanceView(APIView):
    """
    GET /api/attendance/my/?month=&year=
    Returns the logged-in worker's own attendance logs for a given month.
    Workers can only see their own records.
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
    Returns total_days, total_hours, overtime + full logs list.
    Worker only sees their own data.
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
    Returns the currently open (clocked-in) record for the logged-in worker.
    Used by the app on startup to restore timer state if app was closed mid-shift.
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
            # Shouldn't happen but handle gracefully
            record = AttendanceRecord.objects.filter(worker=worker, status='open').last()
            return Response({
                'open':      True,
                'record_id': record.id,
                'clock_in':  record.clock_in.isoformat(),
            })


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS — WORKER VIEW
# ══════════════════════════════════════════════════════════════════════════════

class MyProjectsView(APIView):
    """
    GET /api/projects/my/
    Returns active projects assigned to the logged-in worker.
    Filtered to only what this worker is assigned to.
    Managers get all active projects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_manager:
            projects = (
                Project.objects
                .prefetch_related('files', 'workers')
                .filter(status='active')
                .order_by('-created_at')
            )
        else:
            worker = _get_worker(user)
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
    Returns blueprint, map, and document files for a project.
    Used by the slide-down panel in the Projects screen.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        files = (
            ProjectFile.objects
            .filter(
                project_id=pk,
                file_type__in=['blueprint', 'map', 'document'],
            )
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


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT WORK LOGS (Boss Notes)
# ══════════════════════════════════════════════════════════════════════════════

class ProjectNotesView(APIView):
    """
    GET  /api/projects/<pk>/notes/          — list today's + recent notes
    POST /api/projects/<pk>/notes/          — manager creates a note
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Default: today's note, fallback to last 7 days
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
            project=project,
            log_date=log_date,
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


# ══════════════════════════════════════════════════════════════════════════════
# SITE PHOTOS
# ══════════════════════════════════════════════════════════════════════════════

class SitePhotoUploadView(APIView):
    """
    POST /api/projects/<pk>/photos/
    Multipart: { photo (file), caption? }
    Worker uploads a site or invoice photo linked to a project.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            project = Project.objects.get(id=pk)
        except Project.DoesNotExist:
            return Response({'error': 'פרויקט לא נמצא'}, status=404)

        worker = _get_worker(request.user)
        photo_file = request.FILES.get('photo')
        if not photo_file:
            return Response({'error': 'לא נשלחה תמונה'}, status=400)

        photo = ProjectSitePhoto.objects.create(
            project  = project,
            photo    = photo_file,
            caption  = request.data.get('caption', ''),
            taken_by = worker,
        )

        return Response({
            'id':      photo.id,
            'url':     request.build_absolute_uri(photo.photo.url),
            'caption': photo.caption,
            'taken_at': photo.taken_at.isoformat(),
        }, status=201)

    def get(self, request, pk):
        """GET /api/projects/<pk>/photos/ — list project site photos."""
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


# ══════════════════════════════════════════════════════════════════════════════
# PAYSLIPS — WORKER SELF-SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class MyPayslipsView(APIView):
    """
    GET /api/payroll/my/?year=
    Returns the logged-in worker's own PayrollRecords.
    Workers see only their own. Managers should use /api/payroll/ with worker_id filter.
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
# DOCUMENTS — WORKER SELF-SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class MyDocumentsView(APIView):
    """
    GET /api/documents/my/
    Returns document-type files from projects the worker is assigned to.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response([])

        if request.user.is_manager:
            project_ids = list(Project.objects.values_list('id', flat=True))
        else:
            project_ids = list(worker.projects.values_list('id', flat=True))

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
# MY INVOICES — WORKER SELF-SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class MyInvoicesView(APIView):
    """
    GET  /api/invoices/my/?status=
    POST /api/invoices/my/         — worker submits a material invoice/photo
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request):
        worker = _get_worker(request.user)
        if not worker:
            return Response([])

        qs = MaterialInvoice.objects.filter(worker=worker).order_by('-submitted_at')
        status_filter = request.query_params.get('status')
        if status_filter:
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

        amount_raw = request.data.get('amount', '0')
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            return Response({'error': 'סכום לא תקין'}, status=400)

        date_raw = request.data.get('invoice_date', date.today().isoformat())
        try:
            inv_date = date.fromisoformat(date_raw)
        except ValueError:
            inv_date = date.today()

        project_id = request.data.get('project')
        project = None
        if project_id:
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
# MANAGER DASHBOARD EXTRAS
# ══════════════════════════════════════════════════════════════════════════════

class DashboardView(APIView):
    """
    GET /api/dashboard/
    Manager-only overview: who's clocked in, pending invoices, today's summary.
    """
    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        now   = timezone.now()
        today = now.date()

        # Currently clocked in
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

        # Today's completed shifts
        today_closed = AttendanceRecord.objects.filter(
            clock_in__date=today, status__in=['closed', 'approved']
        ).aggregate(
            count=Count('id'),
            total_hours=Sum('hours_worked'),
        )

        # Pending invoices
        pending_invoices = MaterialInvoice.objects.filter(status='pending').count()

        # Active workers count
        active_workers = Worker.objects.filter(is_active=True).count()

        # Active projects count
        active_projects = Project.objects.filter(status='active').count()

        return Response({
            'clocked_in_now':     clocked_in,
            'clocked_in_count':   len(clocked_in),
            'today_shifts':       today_closed['count'] or 0,
            'today_hours':        float(today_closed['total_hours'] or 0),
            'pending_invoices':   pending_invoices,
            'active_workers':     active_workers,
            'active_projects':    active_projects,
            'date':               today.isoformat(),
            'time':               now.strftime('%H:%M'),
        })
