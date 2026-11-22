from django.urls import path
from .views import (
    vendor_list_view, vendor_create_view, vendor_update_view, vendor_detail_view, vendor_delete_view,
    vendor_contact_add_view, vendor_contact_delete_view,
    contract_list_view, contract_create_view, contract_update_view, contract_detail_view,
    rma_list_view, rma_create_view, rma_update_view,
    vendor_evaluation_create_view, vendor_document_upload_view,
    export_vendors_excel
)

urlpatterns = [
    # Vendors Master Directory
    path('', vendor_list_view, name='vendor_list'),
    path('create/', vendor_create_view, name='vendor_create'),
    path('<int:pk>/', vendor_detail_view, name='vendor_detail'),
    path('<int:pk>/edit/', vendor_update_view, name='vendor_update'),
    path('<int:pk>/delete/', vendor_delete_view, name='vendor_delete'),

    # Contacts, Evaluations, Documents
    path('<int:vendor_pk>/contacts/add/', vendor_contact_add_view, name='vendor_contact_add'),
    path('contacts/<int:pk>/delete/', vendor_contact_delete_view, name='vendor_contact_delete'),
    path('<int:vendor_pk>/evaluations/add/', vendor_evaluation_create_view, name='vendor_evaluation_add'),
    path('<int:vendor_pk>/documents/upload/', vendor_document_upload_view, name='vendor_document_upload'),

    # Contracts & AMCs
    path('contracts/', contract_list_view, name='contract_list'),
    path('contracts/create/', contract_create_view, name='contract_create'),
    path('contracts/<int:pk>/', contract_detail_view, name='contract_detail'),
    path('contracts/<int:pk>/edit/', contract_update_view, name='contract_update'),

    # RMA & Repairs
    path('rma/', rma_list_view, name='rma_list'),
    path('rma/create/', rma_create_view, name='rma_create'),
    path('rma/<int:pk>/edit/', rma_update_view, name='rma_update'),

    # Exports
    path('export/excel/', export_vendors_excel, name='export_vendors_excel'),
]
