from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.locations.models import Location


class Command(BaseCommand):
    help = "Seeds standard role-based test users for development, QA, and demonstration."

    def handle(self, *args, **options):
        # 1. Super Admin
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@akij.net',
                'first_name': 'IT System',
                'last_name': 'Administrator',
                'is_superuser': True,
                'is_staff': True,
                'is_active': True,
            }
        )
        admin.email = 'admin@akij.net'
        admin.set_password('admin123')
        admin.save()
        p_admin, _ = UserProfile.objects.get_or_create(user=admin)
        p_admin.role = UserProfile.Role.SUPER_ADMIN
        p_admin.designation = 'Chief Information Officer (CIO)'
        p_admin.save()

        # 2. Central Auditor (HO Admin)
        auditor, _ = User.objects.get_or_create(
            username='auditor',
            defaults={
                'email': 'auditor@akij.net',
                'first_name': 'Central IT',
                'last_name': 'Auditor',
                'is_staff': False,
                'is_active': True,
            }
        )
        auditor.email = 'auditor@akij.net'
        auditor.set_password('audit123')
        auditor.save()
        p_auditor, _ = UserProfile.objects.get_or_create(user=auditor)
        p_auditor.role = UserProfile.Role.HO_ADMIN
        p_auditor.designation = 'Lead IT Auditor'
        p_auditor.save()

        # 3. Sir / Management (HO Admin)
        sir, _ = User.objects.get_or_create(
            username='sir',
            defaults={
                'email': 'director@akij.net',
                'first_name': 'Managing',
                'last_name': 'Director',
                'is_staff': False,
                'is_active': True,
            }
        )
        sir.email = 'director@akij.net'
        sir.set_password('sir123')
        sir.save()
        p_sir, _ = UserProfile.objects.get_or_create(user=sir)
        p_sir.role = UserProfile.Role.HO_ADMIN
        p_sir.designation = 'Executive Management'
        p_sir.save()

        # 4. Factory Admin (APL Factory Chattak)
        factory, _ = User.objects.get_or_create(
            username='factory_admin',
            defaults={
                'email': 'factory@akij.net',
                'first_name': 'Chattak Factory',
                'last_name': 'In-Charge',
                'is_staff': False,
                'is_active': True,
            }
        )
        factory.email = 'factory@akij.net'
        factory.set_password('factory123')
        factory.save()
        p_factory, _ = UserProfile.objects.get_or_create(user=factory)
        p_factory.role = UserProfile.Role.FACTORY_ADMIN
        p_factory.designation = 'Factory IT Officer'
        p_factory.save()
        chattak = Location.objects.filter(name__icontains='Chattak').first()
        if chattak:
            p_factory.assigned_locations.add(chattak)

        # 5. Depot Admin (Bogura & Chattogram Depots)
        depot, _ = User.objects.get_or_create(
            username='depot_admin',
            defaults={
                'email': 'depot@akij.net',
                'first_name': 'Regional Depot',
                'last_name': 'Administrator',
                'is_staff': False,
                'is_active': True,
            }
        )
        depot.email = 'depot@akij.net'
        depot.set_password('depot123')
        depot.save()
        p_depot, _ = UserProfile.objects.get_or_create(user=depot)
        p_depot.role = UserProfile.Role.DEPOT_ADMIN
        p_depot.designation = 'Depot IT Executive'
        p_depot.save()
        bogura = Location.objects.filter(name__icontains='Bogura').first()
        ctg = Location.objects.filter(name__icontains='Chattogram').first()
        if bogura:
            p_depot.assigned_locations.add(bogura)
        if ctg:
            p_depot.assigned_locations.add(ctg)

        self.stdout.write(self.style.SUCCESS("Successfully seeded role-based test users!"))
