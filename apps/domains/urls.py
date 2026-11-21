from django.urls import path
from . import views

urlpatterns = [
    path('', views.domain_list_view, name='domain_list'),
    path('new/', views.domain_create_or_edit_view, name='domain_create'),
    path('<int:pk>/edit/', views.domain_create_or_edit_view, name='domain_edit'),
    path('<int:pk>/', views.domain_detail_view, name='domain_detail'),
    path('<int:pk>/delete/', views.domain_delete_view, name='domain_delete'),
]
