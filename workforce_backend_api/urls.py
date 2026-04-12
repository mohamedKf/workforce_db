# core/urls.py  —  complete, with all mobile endpoints added
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    # Auth
    LoginView, RegisterView, PinLoginView, SetPinView, MeView, ChangePasswordView,
    # Workers
    WorkerListCreateView, WorkerDetailView, WorkerChildrenView, RecalcTaxPointsView,
    Form101View, Form106ListView, Form106DetailView,
    # Projects
    ProjectListCreateView, ProjectDetailView, ProjectAssignWorkersView,
    ProjectFileView, ProjectFileDeleteView,
    # Attendance
    ClockInView, ClockOutView, AttendanceListView, AttendanceDetailView,
    OpenAttendanceView, MonthlySummaryView,
    # Payroll
    PayrollCalculateView, PayrollListView, PayrollDetailView,
    # Invoices
    InvoiceListCreateView, InvoiceDetailView, InvoiceReviewView,
    # Freelancers
    FreelancerListCreateView, FreelancerDetailView,
    FreelancerPaymentListView, FreelancerPaymentDetailView,
)
from .views_mobile import (
    # Auth extras
    WorkerProfileView,
    # Attendance self-service
    MyAttendanceView, MyMonthlySummaryView, MyOpenAttendanceView,
    # Projects worker view
    MyProjectsView, ProjectBlueprintsView, ProjectNotesView,
    SitePhotoUploadView,
    # Payslips & documents
    MyPayslipsView, MyDocumentsView,
    # Invoices self-service
    MyInvoicesView,
    # Dashboard
    DashboardView,
)

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/login/',            LoginView.as_view()),
    path('auth/register/',         RegisterView.as_view()),
    path('auth/login-pin/',        PinLoginView.as_view()),
    path('auth/refresh/',          TokenRefreshView.as_view()),
    path('auth/set-pin/',          SetPinView.as_view()),
    path('auth/me/',               MeView.as_view()),
    path('auth/change-password/',  ChangePasswordView.as_view()),
    path('auth/worker-profile/',   WorkerProfileView.as_view()),   # ★ NEW

    # ── Workers ───────────────────────────────────────────────────────────────
    path('workers/',                          WorkerListCreateView.as_view()),
    path('workers/<int:pk>/',                 WorkerDetailView.as_view()),
    path('workers/<int:pk>/children/',        WorkerChildrenView.as_view()),
    path('workers/<int:pk>/recalc-tax/',      RecalcTaxPointsView.as_view()),
    path('workers/<int:pk>/form101/',         Form101View.as_view()),
    path('workers/<int:pk>/form106/',         Form106ListView.as_view()),
    path('form106/<int:pk>/',                 Form106DetailView.as_view()),

    # ── Projects ──────────────────────────────────────────────────────────────
    path('projects/',                         ProjectListCreateView.as_view()),
    path('projects/my/',                      MyProjectsView.as_view()),              # ★ NEW
    path('projects/<int:pk>/',                ProjectDetailView.as_view()),
    path('projects/<int:pk>/assign/',         ProjectAssignWorkersView.as_view()),
    path('projects/<int:pk>/files/',          ProjectFileView.as_view()),
    path('projects/<int:pk>/blueprints/',     ProjectBlueprintsView.as_view()),       # ★ NEW
    path('projects/<int:pk>/notes/',          ProjectNotesView.as_view()),            # ★ NEW
    path('projects/<int:pk>/photos/',         SitePhotoUploadView.as_view()),         # ★ NEW
    path('project-files/<int:pk>/',           ProjectFileDeleteView.as_view()),

    # ── Attendance ────────────────────────────────────────────────────────────
    path('attendance/',                       AttendanceListView.as_view()),
    path('attendance/clock-in/',              ClockInView.as_view()),
    path('attendance/clock-out/<int:record_id>/', ClockOutView.as_view()),
    path('attendance/open/',                  OpenAttendanceView.as_view()),
    path('attendance/summary/',               MonthlySummaryView.as_view()),
    path('attendance/my/',                    MyAttendanceView.as_view()),            # ★ NEW
    path('attendance/my-summary/',            MyMonthlySummaryView.as_view()),        # ★ NEW
    path('attendance/my-open/',               MyOpenAttendanceView.as_view()),        # ★ NEW
    path('attendance/<int:pk>/',              AttendanceDetailView.as_view()),

    # ── Payroll ───────────────────────────────────────────────────────────────
    path('payroll/',                          PayrollListView.as_view()),
    path('payroll/calculate/',                PayrollCalculateView.as_view()),
    path('payroll/my/',                       MyPayslipsView.as_view()),              # ★ NEW
    path('payroll/<int:pk>/',                 PayrollDetailView.as_view()),

    # ── Invoices ──────────────────────────────────────────────────────────────
    path('invoices/',                         InvoiceListCreateView.as_view()),
    path('invoices/my/',                      MyInvoicesView.as_view()),              # ★ NEW
    path('invoices/<int:pk>/',                InvoiceDetailView.as_view()),
    path('invoices/<int:pk>/review/',         InvoiceReviewView.as_view()),

    # ── Freelancers ───────────────────────────────────────────────────────────
    path('freelancers/',                      FreelancerListCreateView.as_view()),
    path('freelancers/<int:pk>/',             FreelancerDetailView.as_view()),
    path('freelancers/<int:pk>/payments/',    FreelancerPaymentListView.as_view()),
    path('payments/<int:pk>/',                FreelancerPaymentDetailView.as_view()),

    # ── Documents ─────────────────────────────────────────────────────────────
    path('documents/my/',                     MyDocumentsView.as_view()),             # ★ NEW

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/',                        DashboardView.as_view()),               # ★ NEW
]
