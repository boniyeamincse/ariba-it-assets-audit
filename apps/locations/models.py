from django.db import models
from apps.common.models import TimeStampedModel

class Company(TimeStampedModel):
    name = models.CharField(max_length=150, default="Akij Group")
    short_code = models.CharField(max_length=20, default="AKIJ", unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class Location(TimeStampedModel):
    LOCATION_TYPES = (
        ('HEAD_OFFICE', 'Head Office'),
        ('FACTORY', 'Factory'),
        ('WAREHOUSE', 'Warehouse'),
        ('DEPOT', 'Depot'),
        ('BRANCH', 'Branch'),
    )

    DIVISION_CHOICES = (
        ('Dhaka', 'Dhaka'),
        ('Chattogram', 'Chattogram'),
        ('Sylhet', 'Sylhet'),
        ('Rajshahi', 'Rajshahi'),
        ('Khulna', 'Khulna'),
        ('Barishal', 'Barishal'),
        ('Rangpur', 'Rangpur'),
        ('Mymensingh', 'Mymensingh'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='locations')
    location_id = models.CharField(max_length=30, unique=True, null=True, blank=True, verbose_name="Location ID", db_index=True)
    name = models.CharField(max_length=150, verbose_name="Location Name")
    code = models.CharField(max_length=50, unique=True, verbose_name="Location Code")
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='FACTORY', verbose_name="Location Type")
    address = models.TextField(blank=True, null=True, verbose_name="Address")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    division = models.CharField(max_length=50, choices=DIVISION_CHOICES, blank=True, null=True, verbose_name="Division")
    parent_location = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_locations', verbose_name="Parent Location")
    contact_person = models.CharField(max_length=120, blank=True, null=True, verbose_name="Contact Person")
    contact_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Contact Number")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    # is_active (Status: Active / Inactive) is inherited from TimeStampedModel

    class Meta:
        ordering = ['location_type', 'name']

    @property
    def in_charge_name(self):
        return self.contact_person or ""

    @in_charge_name.setter
    def in_charge_name(self, val):
        self.contact_person = val

    @property
    def in_charge_phone(self):
        return self.contact_number or ""

    @in_charge_phone.setter
    def in_charge_phone(self, val):
        self.contact_number = val

    def save(self, *args, **kwargs):
        if not self.location_id:
            count = Location.objects.count() + 1
            candidate = f"LOC-{count:03d}"
            while Location.objects.filter(location_id=candidate).exists():
                count += 1
                candidate = f"LOC-{count:03d}"
            self.location_id = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        lid = self.location_id or f"ID-{self.id}"
        return f"[{lid}] {self.name} ({self.get_location_type_display()})"

    def to_dict(self):
        return {
            'id': self.id,
            'location_id': self.location_id or f"LOC-{self.id:03d}",
            'name': self.name,
            'code': self.code,
            'type': self.location_type,
            'type_display': self.get_location_type_display(),
            'address': self.address or '',
            'city': self.city or '',
            'division': self.division or '',
            'parent_location': self.parent_location.name if self.parent_location else None,
            'contact_person': self.contact_person or '',
            'contact_number': self.contact_number or '',
            'is_active': self.is_active,
            'description': self.description or '',
        }
