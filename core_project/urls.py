from django.contrib import admin
from django.urls import path, include
from apps.accounts import administration
from apps.accounts.access import Role, roles_required
from apps.accounts.views import login_view, logout_view
from apps.reports.views import dashboard_view, matrix_view, export_excel_matrix
from apps.common.views import activity_log_view
from apps.locations.views import location_list_view, location_create_or_edit_view
from apps.devices.views import (
    asset_list_view,
    asset_create_or_edit_view,
    category_list_view,
    asset_detail_view,
    asset_label_qr_view,
    asset_retire_view,
    asset_import_csv_view,
    download_sample_asset_csv_view,
    software_list_view,
)
from apps.audits.views import (
    audit_list_view,
    audit_detail_view,
    audit_print_view,
    audit_create_or_edit_view,
)

urlpatterns = [
    path('admin/dashboard/', administration.dashboard_entry, name='dashboard'),
    path('admin/super/dashboard/', roles_required(Role.SUPER_ADMIN)(dashboard_view), name='super_dashboard'),
    path('admin/ho/dashboard/', roles_required(Role.HO_ADMIN)(dashboard_view), name='ho_dashboard'),
    path('admin/factory/dashboard/', roles_required(Role.FACTORY_ADMIN)(dashboard_view), name='factory_dashboard'),
    path('admin/depot/dashboard/', roles_required(Role.DEPOT_ADMIN)(dashboard_view), name='depot_dashboard'),
    path('admin/users/', administration.user_list, name='administration_users'),
    path('admin/users/new/', administration.user_editor, name='administration_user_create'),
    path('admin/users/<int:user_id>/edit/', administration.user_editor, name='administration_user_edit'),
    path('admin/roles/', administration.roles_view, name='administration_roles'),
    path('admin/roles/new/', administration.role_create, name='administration_role_create'),
    path('admin/activity/', activity_log_view, name='activity_logs'),
    path('admin/settings/', administration.settings_view, name='administration_settings'),
    path('admin/settings/asset-id/preview/', administration.asset_id_preview, name='asset_id_preview'),
    path('admin/settings/<slug:section>/', administration.settings_view, name='administration_settings_section'),
    path('admin/', admin.site.urls),
    
    # Authentication (Login / Logout)
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # Executive Dashboard
    path('', administration.dashboard_entry, name='home'),
    
    # Locations Management
    path('locations/', location_list_view, name='location_list'),
    path('locations/new/', location_create_or_edit_view, name='location_create'),
    path('locations/<int:loc_id>/edit/', location_create_or_edit_view, name='location_edit'),

    # Assets Management (Location-Wise Dynamic Hardware Tracking)
    path('assets/', asset_list_view, name='asset_list'),
    path('assets/new/', asset_create_or_edit_view, name='asset_create'),
    path('assets/import-csv/', asset_import_csv_view, name='asset_import_csv'),
    path('assets/sample-csv/', download_sample_asset_csv_view, name='asset_sample_csv'),
    path('assets/<int:asset_id>/edit/', asset_create_or_edit_view, name='asset_edit'),
    path('assets/<int:asset_id>/delete/', asset_retire_view, name='asset_delete'),
    path('assets/<int:asset_id>/retire/', asset_retire_view, name='asset_retire'),
    path('assets/<int:asset_id>/label-qr.svg', asset_label_qr_view, name='asset_label_qr'),
    path('assets/<int:asset_id>/', asset_detail_view, name='asset_detail'),
    path('assets/categories/', category_list_view, name='category_list'),
    path('software/', software_list_view, name='software_list'),
    path('domains/', include('apps.domains.urls')),

    # Multi-Location Master Matrix
    path('matrix/', matrix_view, name='matrix'),
    path('matrix/export-excel/', export_excel_matrix, name='export_excel_matrix'),
    
    # Audits
    path('audits/', audit_list_view, name='audit_list'),
    path('audits/new/', audit_create_or_edit_view, name='audit_create'),
    path('audits/<int:audit_id>/', audit_detail_view, name='audit_detail'),
    path('audits/<int:audit_id>/edit/', audit_create_or_edit_view, name='audit_edit'),
    path('audits/<int:audit_id>/print/', audit_print_view, name='audit_print'),
    # Enterprise System Activity & Audit Logs
    path('logs/', activity_log_view, name='legacy_activity_logs'),
]
