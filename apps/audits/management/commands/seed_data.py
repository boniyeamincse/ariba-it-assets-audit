from django.core.management.base import BaseCommand
from datetime import date
from apps.locations.models import Company, Location
from apps.devices.models import DeviceCategory, DeviceType
from apps.audits.models import AuditSession, AuditItem

class Command(BaseCommand):
    help = "Populate master IT catalog, locations, and initial APL Factory Chattak audit data."

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

        loc_objs = {}
        for name, code, loc_type, addr, incharge in locations_data:
            loc, _ = Location.objects.get_or_create(
                code=code,
                defaults={
                    "company": company,
                    "name": name,
                    "location_type": loc_type,
                    "address": addr,
                    "in_charge_name": incharge
                }
            )
            loc_objs[code] = loc

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

        infra_device_objs = {}
        for order, d_name in infra_devices:
            dev, _ = DeviceType.objects.get_or_create(
                category=cat_infra,
                name=d_name,
                defaults={"order": order}
            )
            infra_device_objs[d_name] = dev

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

        user_device_objs = {}
        for order, d_name in user_devices:
            dev, _ = DeviceType.objects.get_or_create(
                category=cat_users,
                name=d_name,
                defaults={"order": order}
            )
            user_device_objs[d_name] = dev

        # 5. Populate APL Factory Chattak Audit Session (Exact quantities from photos)
        chattak_loc = loc_objs["APL-CHATTAK"]
        audit_session, _ = AuditSession.objects.get_or_create(
            location=chattak_loc,
            audit_date=date(2026, 11, 21),
            defaults={
                "auditor_name": "IT Audit Team",
                "verified_by_name": "Factory In-Charge",
                "approved_by_name": "Executive Director / Sir",
                "status": "APPROVED",
                "remarks": "Comprehensive physical IT asset verification completed at Chattak Factory."
            }
        )

        # Infrastructure Quantities from Image 2
        infra_counts = {
            "Microtik Router": 1,
            "Core Switch": 3,
            "Managed Switch": 12,
            "Unmanaged Switch": 8,
            "Network Rack": 16,
            "NVR": 3,
            "IP Camera": 124,
            "CCTV Monitor": 4,
            "Wireless Mouse": 4,
            "UniFi AP": 15,
            "Access Control": 8,
            "Server Desktop": 1,
            "All In one PC": 1,
            "Projector": 2,
            "IPS Full Set": 1,
            "Card Printer": 1,
            "Laminating Machine": 1,
            "Wireless SoundBox": 1,
            "PA System Controller Rack": 1,
            "Remote Mic Controller": 2
        }

        for dev_name, qty in infra_counts.items():
            dev = infra_device_objs[dev_name]
            AuditItem.objects.update_or_create(
                audit_session=audit_session,
                device_type=dev,
                defaults={
                    "active_qty": qty,
                    "backup_qty": 0,
                    "faulty_qty": 0,
                    "total_qty": qty,
                    "remarks": ""
                }
            )

        # Users Quantities from Image 1
        user_counts = {
            "Laptop": (40, 0, 0),
            "Backup Laptop": (0, 2, 0),
            "Desktop": (35, 0, 0),
            "Monitor": (36, 0, 0),
            "Backup Monitor": (0, 1, 0),
            "Usb Mouse": (49, 0, 0),
            "Usb Kyboard": (35, 0, 0),
            "Usb Hub": (5, 0, 0),
            "HeadPhone": (14, 0, 0),
            "Laser Printer": (12, 0, 0),
            "Colour Printer": (1, 0, 0),
            "MRP Printer": (2, 0, 0),
            "Voucher Printer": (1, 0, 0),
            "Dotmatrix Vat Printer": (2, 0, 0),
            "Backup Printer": (0, 2, 0),
            "Scanner": (11, 0, 0),
            "Speed Scanner": (1, 0, 0),
            "Backup Scanner": (0, 1, 0)
        }

        for dev_name, (act, bak, flt) in user_counts.items():
            dev = user_device_objs[dev_name]
            tot = act + bak + flt
            AuditItem.objects.update_or_create(
                audit_session=audit_session,
                device_type=dev,
                defaults={
                    "active_qty": act,
                    "backup_qty": bak,
                    "faulty_qty": flt,
                    "total_qty": tot,
                    "remarks": ""
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded database! Audit for {chattak_loc.name} created with "
            f"{audit_session.items.count()} items (Total count: {audit_session.total_qty} devices)."
        ))
