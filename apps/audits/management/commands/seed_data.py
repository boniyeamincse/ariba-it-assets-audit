from django.core.management.base import BaseCommand
from apps.locations.models import Company, Location
from apps.devices.models import DeviceCategory, DeviceType

class Command(BaseCommand):
    help = "Populate the initial company, locations, and master device catalog."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting database seeding..."))

        # 1. Company
        company, _ = Company.objects.get_or_create(
            short_code="APL",
            defaults={"name": "Akij Plastics Ltd", "description": "Akij Group Sister Concern"}
        )

        # 2. Locations
        locations_data = [
            ("APL Head Office", "APL-HQ", "HEAD_OFFICE", "Akij House, Dhaka", "IT Department Head"),
            ("APL Factory Chattak", "APL-CHATTAK", "FACTORY", "Chattak, Sunamganj", "Factory In-Charge"),
            ("Bogura Regional Depot", "APL-DEPOT-BOG", "DEPOT", "Bogura Distribution Center", "Depot Manager"),
            ("Chattogram Depot", "APL-DEPOT-CTG", "DEPOT", "Agrabad, Chattogram", "Depot Manager"),
        ]

        for name, code, loc_type, addr, incharge in locations_data:
            Location.objects.get_or_create(
                code=code,
                defaults={
                    "company": company,
                    "name": name,
                    "location_type": loc_type,
                    "address": addr,
                    "in_charge_name": incharge
                }
            )

        # 3. Categories
        cat_infra, _ = DeviceCategory.objects.get_or_create(
            code="INFRASTRUCTURE",
            defaults={"name": "Infrastructure Devices", "order": 1}
        )
        cat_users, _ = DeviceCategory.objects.get_or_create(
            code="USERS",
            defaults={"name": "Users / End-User Devices", "order": 2}
        )

        # 4. Master Devices
        infra_devices = [
            (1, "Microtik Router"),
            (2, "Core Switch"),
            (3, "Managed Switch"),
            (4, "Unmanaged Switch"),
            (5, "Network Rack"),
            (6, "NVR"),
            (7, "IP Camera"),
            (8, "CCTV Monitor"),
            (9, "Wireless Mouse"),
            (10, "UniFi AP"),
            (11, "Access Control"),
            (12, "Server Desktop"),
            (13, "All In one PC"),
            (14, "Projector"),
            (15, "IPS Full Set"),
            (16, "Card Printer"),
            (17, "Laminating Machine"),
            (18, "Wireless SoundBox"),
            (19, "PA System Controller Rack"),
            (20, "Remote Mic Controller"),
        ]

        for order, d_name in infra_devices:
            DeviceType.objects.get_or_create(
                category=cat_infra,
                name=d_name,
                defaults={"order": order}
            )

        user_devices = [
            (1, "Laptop"),
            (2, "Backup Laptop"),
            (3, "Desktop"),
            (4, "Monitor"),
            (5, "Backup Monitor"),
            (6, "Usb Mouse"),
            (7, "Usb Kyboard"),
            (8, "Usb Hub"),
            (9, "HeadPhone"),
            (10, "Laser Printer"),
            (11, "Colour Printer"),
            (12, "MRP Printer"),
            (13, "Voucher Printer"),
            (14, "Dotmatrix Vat Printer"),
            (15, "Backup Printer"),
            (16, "Scanner"),
            (17, "Speed Scanner"),
            (18, "Backup Scanner"),
        ]

        for order, d_name in user_devices:
            DeviceType.objects.get_or_create(
                category=cat_users,
                name=d_name,
                defaults={"order": order}
            )
        self.stdout.write(self.style.SUCCESS("Master company, locations, and device catalog are ready."))
