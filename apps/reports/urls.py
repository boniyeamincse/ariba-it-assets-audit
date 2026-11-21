from django.urls import path
from . import views

urlpatterns = [
    # Reports Hub
    path('', views.report_hub_view, name='report_hub'),
    
    # 1. Asset Inventory & Lifecycle Report
    path('assets/', views.report_asset_inventory_view, name='report_asset_inventory'),
    path('assets/export-excel/', views.export_report_asset_excel, name='report_asset_excel'),
    
    # 2. Software Compliance & Cyber Risk Report
    path('software-compliance/', views.report_software_compliance_view, name='report_software_compliance'),
    path('software-compliance/export-excel/', views.export_report_software_excel, name='report_software_excel'),
    
    # 3. Domains, DNS & SSL Governance Report
    path('domains-ssl/', views.report_domains_ssl_view, name='report_domains_ssl'),
    path('domains-ssl/export-excel/', views.export_report_domains_excel, name='report_domains_excel'),
    
    # 4. Physical Audit Reconciliation Report
    path('audit-reconciliation/', views.report_audit_reconciliation_view, name='report_audit_reconciliation'),
    path('audit-reconciliation/export-excel/', views.export_report_audit_excel, name='report_audit_excel'),
]
