from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.urls import reverse


class TechnicalAdminSite(AdminSite):
    def has_permission(self, request):
        return super().has_permission(request) and request.user.is_superuser

    def login(self, request, extra_context=None):
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(reverse('admin:index'), reverse('login'))


class TechnicalAdminConfig(AdminConfig):
    default_site = 'apps.accounts.admin_site.TechnicalAdminSite'
