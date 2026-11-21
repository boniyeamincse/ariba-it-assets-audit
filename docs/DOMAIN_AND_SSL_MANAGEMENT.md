# Domain, DNS & SSL Certificate Management Module Specification
**Enterprise IT Asset Audit & Multi-Location Inventory System**  
**Organization:** Akij Group (Plastics, Cement, Jute, Food & Beverage, Motors, Corporate)  
**Document Type:** Functional, Architectural & Technical Module Specification  
**Version:** 1.0 | **Status:** Proposed & Approved Architecture  

---

## ১. মডিউল পরিচিতি ও ব্যবসায়িক লক্ষ্য (Executive Overview & Business Objectives)

একটি বৃহৎ শিল্পগোষ্ঠীতে (Group of Companies) শত শত ফিজিক্যাল হার্ডওয়্যার এবং সফটওয়্যার লাইসেন্সের পাশাপাশি **ডিজিটাল আইডেন্টিটি ও ওয়েব অবকাঠামো (Web & Domain Infrastructure)** একটি অত্যন্ত গুরুত্বপূর্ণ অ্যাসেট। 

আকিজ গ্রুপের মতো কনগ্লোমারেটে বিভিন্ন সিস্টার কনসার্ন, করপোরেট পোর্টাল, ইআরপি ক্লাউড গেটওয়ে, ই-কমার্স সাইট এবং ব্র্যান্ড ল্যান্ডিং পেজের জন্য **৫০ থেকে ২০০+ ডোমেইন** নিবন্ধিত থাকে। অধিকাংশ প্রতিষ্ঠানে বিভিন্ন সময়ে বিভিন্ন রেজিস্ট্রার (যেমন: GoDaddy, Namecheap, BTCL `.com.bd`, Cloudflare, AWS Route 53) থেকে ডোমেইন কেনা হয় এবং ভিন্ন ভিন্ন ব্যক্তি/আইটি অফিসারের ব্যক্তিগত বা ডিপার্টমেন্টাল ইমেইল দিয়ে এগুলো রেজিস্টার করা থাকে।

### সেন্ট্রাল ডোমেইন ম্যানেজমেন্ট না থাকার প্রধান ঝুঁকিগুলো:
1. **ডোমেইন এক্সপায়ারি ডিজাস্টার (Critical Downtime):**
   - ডোমেইনের রিনিউ তারিখ মিস হয়ে গেলে **কোম্পানির সব প্রাতিষ্ঠানিক ইমেইল (Google Workspace / Microsoft 365) আদান-প্রদান সাথে সাথে বন্ধ হয়ে যায়**, ওয়েবসাইট ও কাস্টমার পোর্টাল ডাউন হয়ে যায়।
2. **ডোমেইন হাইজ্যাকিং ও স্কোয়াটিং (Brand Hijacking Risk):**
   - এক্সপায়ার হওয়া ডোমেইন ড্রপ হলে সাইবার ক্রিমিনাল বা প্রতিযোগী প্রতিষ্ঠান তা কিনে নিয়ে আকিজ গ্রুপের ব্র‍্যান্ডের অপব্যবহার করতে পারে।
3. **SSL / TLS সার্টিফিকেট এক্সপায়ারি:**
   - ব্রাউজারে *"Your connection is not private / Security Warning"* প্রদর্শন করে, যা গ্রাহকের আস্থা ও করপোরেট ভাবমূর্তি নষ্ট করে।
4. **রেজিস্ট্রার ও বিলিং বিশৃঙ্খলা (Billing Sprawl):**
   - কোন ডোমেইন কার ক্রেডিট কার্ড বা ইনভয়েসে কত ডলারে/টাকায় রিনিউ হচ্ছে এবং কখন রিনিউ করতে হবে তার সেন্ট্রাল হিসাব না থাকা।
5. **DNS & হোস্টিং ট্র্যাকিংয়ের অভাব:**
   - ডোমেইনের ট্রাফিক কোন ক্লাউড ভিপিএস (AWS, DigitalOcean) বা অন-প্রেমিসেস ডেটাসেন্টারের কোন লাইভ আইপিতে পয়েন্ট করা রয়েছে তা অজানা থাকা।

**Domain & SSL Management** মডিউলটির মূল লক্ষ্য হলো গ্রুপের সকল ডোমেইন, সাব-ডোমেইন, ডিএনএস প্রোভাইডার, এসএসএল সার্টিফিকেট এবং রিনিউয়াল লাইফসাইকেল এক ছাতার নিচে স্বয়ংক্রিয়ভাবে ট্র্যাক করা।

---

## ২. সিস্টেম আর্কিটেকচার ও মডিউল পজিশনিং (System Architecture)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   Enterprise IT Asset Audit & SLM Platform                             │
├─────────────────────┬──────────────────────────┬───────────────────────────────────────┤
│ 1. Physical Assets  │ 2. Software & Licensing  │ 3. Domain & SSL Infrastructure       │
│ (Laptops, Desktops, │ (OS, ERP Seats, SaaS,    │ (FQDN, Registrars, DNS Providers,    │
│  Routers, Switches) │  Anti-Virus, Cloud VMs)  │  SSL Certificates, MX Mail Records)   │
└──────────┬──────────┴────────────┬─────────────┴───────────────────┬───────────────────┘
           │                       │                                 │
           ▼                       ▼                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Django Relational Core & Multi-Tenant Isolation                 │
│  - Multi-Company Mapping: Akij Plastics, Akij Cement, Akij Food, Akij Jute, Corporate  │
│  - Multi-Role Access: Super Admin, Central Auditor, Factory/Depot Admins               │
│  - Automated Cron / Expiry Engine: 60/30/15/7/1 Day Expiry Escalation                  │
│  - Immutable Activity Audit Trail: Timestamped change log for any DNS/Expiry updates   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ৩. ডোমেইন ক্লাসিফিকেশন ও শ্রেণিবিন্যাস (Domain Taxonomy)

আকিজ গ্রুপের ডোমেইনগুলোকে নিম্নোক্ত ৫টি ক্যাটাগরিতে ট্র্যাক করা হবে:

| ক্যাটাগরি | বর্ণনা | উদাহরণ (Examples) | ডিফল্ট প্রায়োরিটি |
| :--- | :--- | :--- | :--- |
| **Corporate Primary** | গ্রুপের মূল প্রাতিষ্ঠানিক ও মাদার ডোমেইন | `akij.net`, `akijgroup.com` | **Tier 1 (Mission Critical)** |
| **Business Unit / SBU** | সিস্টার কনসার্নদের প্রাতিষ্ঠানিক ডোমেইন | `akijplastics.com`, `akijcement.com`, `akijjute.com` | **Tier 1 (Mission Critical)** |
| **National ccTLD (.bd)** | বিটিসিএল (BTCL) থেকে নিবন্ধিত দেশীয় ডোমেইন | `akij.com.bd`, `akijplastics.com.bd` | **Tier 1 (Manual Renewal)** |
| **E-Commerce & Digital** | অনলাইন স্টোর, পেমেন্ট গেটওয়ে ও কনজিউমার অ্যাপস | `akijbazaar.com`, `akijflour.com` | **Tier 2 (High)** |
| **ERP / Subdomains / Internal** | ব্যাকঅফিস ইআরপি, অডিট পোর্টাল ও মেইল গেটওয়ে | `erp.akij.net`, `mail.akij.net`, `audit.akij.net` | **Tier 1 (Infrastructure)** |
| **Parked / Defensive** | ব্র‍্যান্ড প্রোটেকশনের জন্য কিনে রাখা সহায়ক ডোমেইন | `akijplastic.com`, `akijgroup.net` | **Tier 3 (Defensive)** |

---

## ৪. ডাটা মডেল ডিজাইন (Data Model Specification: `DomainRecord`)

নতুন অ্যাপ হিসেবে `apps/domains/` অথবা সেন্ট্রাল ইনফ্রাস্ট্রাকচারে নিম্নোক্ত স্কিমায় মডেল তৈরি হবে:

### Model Schema: `DomainRecord`

```python
class DomainRecord(TimeStampedModel):
    # ১. পরিচিতি ও কোম্পানি ম্যাপিং
    domain_name = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        verbose_name="Domain Name (FQDN)",
        help_text="e.g. akijplastics.com"
    )
    company = models.ForeignKey(
        'locations.Company', 
        on_delete=models.PROTECT, 
        related_name='domains',
        verbose_name="Owning Company / SBU"
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='BUSINESS_UNIT',
        db_index=True
    )

    # ২. রেজিস্ট্রার ও অ্যাকাউন্ট ডিটেইলস
    registrar = models.CharField(
        max_length=100,
        choices=REGISTRAR_CHOICES, # GoDaddy, Namecheap, BTCL, Cloudflare, AWS, Hostinger, Other
        verbose_name="Domain Registrar"
    )
    registrar_account_email = models.CharField(
        max_length=150, 
        blank=True, 
        null=True,
        verbose_name="Registrar Account / Owner Email"
    )
    invoice_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Latest Invoice / PO Number"
    )
    annual_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Annual Renewal Cost"
    )
    currency = models.CharField(max_length=10, default="USD")

    # ৩. রেজিস্ট্রেশন লাইফসাইকেল ও মেয়াদ
    registration_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(db_index=True, verbose_name="Domain Expiry Date")
    auto_renewal = models.BooleanField(
        default=True, 
        verbose_name="Auto-Renewal Enabled"
    )

    # ৪. DNS ও হোস্টিং অবকাঠামো
    dns_provider = models.CharField(
        max_length=100, 
        blank=True, 
        choices=DNS_PROVIDER_CHOICES, # Cloudflare, AWS Route 53, cPanel, BTCL DNS, Other
        verbose_name="DNS Management Provider"
    )
    primary_nameserver = models.CharField(max_length=150, blank=True, null=True)
    secondary_nameserver = models.CharField(max_length=150, blank=True, null=True)
    primary_a_record_ip = models.GenericIPAddressField(
        blank=True, 
        null=True, 
        verbose_name="Hosting / Target Web Server IP"
    )
    hosting_provider = models.CharField(
        max_length=120, 
        blank=True, 
        null=True, 
        verbose_name="Hosting Infrastructure / Cloud VPS"
    )
    mail_provider = models.CharField(
        max_length=60, 
        choices=MAIL_PROVIDER_CHOICES, # Google Workspace, Microsoft 365, Zimbra, Zoho, None
        default='MICROSOFT_365'
    )

    # ৫. SSL / TLS সার্টিফিকেট ট্র্যাকিং
    ssl_status = models.CharField(
        max_length=25,
        choices=SSL_STATUS_CHOICES, # ACTIVE, EXPIRING_SOON, EXPIRED, NOT_CONFIGURED
        default='ACTIVE'
    )
    ssl_provider = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="SSL Issuer (DigiCert, Let's Encrypt, Cloudflare)"
    )
    ssl_expiry_date = models.DateField(blank=True, null=True, verbose_name="SSL Expiry Date")

    # ৬. অপারেশনাল স্ট্যাটাস ও অ্যাডমিন
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES, # ACTIVE, EXPIRING_SOON, EXPIRED, PARKED, REDIRECTED
        default='ACTIVE',
        db_index=True
    )
    technical_contact = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        verbose_name="In-Charge IT Officer"
    )
    remarks = models.TextField(blank=True, null=True)
```

---

## ৫. মূল ফিচারসমূহ ও ইউজার ইন্টারফেস (Key Features & UI Layout)

### ১. Domain & SSL Central Hub (`/domains/`)
- **KPI Summary Analytics Cards:**
  - 🌐 **Total Domains Managed** (যেমন: ৪২টি ডোমেইন)
  - ⚠️ **Expiring Within 30 Days** (অ্যাম্বার ওয়ার্নিং ব্যাজ)
  - 🚨 **Expired / Action Required** (রেড ক্রিটিক্যাল অ্যালার্ট)
  - 🔒 **SSL Renewal Pending** (মেয়াদোত্তীর্ণ হতে যাওয়া সার্টিফিকেট)
  - 🔄 **Auto-Renewal Active %** (শতকরা কতটিতে অটো-রিনিউ চালু আছে)

- **মাল্টি-ডাইমেনশনাল ফিল্টার টুলবার:**
  - **Company Filter:** Akij Plastics, Akij Cement, Akij Jute ইত্যাদি অনুযায়ী এক ক্লিকে আলাদা ডোমেইন তালিকা।
  - **Registrar Filter:** GoDaddy, Namecheap, BTCL, Cloudflare ইত্যাদি।
  - **Expiry Filter:** সব ডোমেইন, ৩০ দিনের মধ্যে মেয়াদ শেষ, ৬০ দিনের মধ্যে, অথবা মেয়াদোত্তীর্ণ।
  - **SSL Status Filter:** Active, Expiring, Missing SSL।
  - **Search Bar:** ডোমেইনের নাম, আইপি অ্যাড্রেস, টেকনিক্যাল অফিসার বা ইনভয়েস নম্বর দিয়ে লাইভ সার্চ।

- **ইন্টারেক্টিভ ডাটা টেবিল:**
  - প্রতিটি ডোমেইনের সাথে লাইভ এক্সপায়ারি কাউন্টডাউন ব্যাজ (যেমন: `24 days left`, `Expired 3 days ago`)।
  - SSL সার্টিফিকেট হেলথ আইকন (সবুজ লক / লাল আনলক)।
  - ডিএনএস নেমসার্ভার ও হোস্টিং আইপি দ্রুত কপি করার বোতাম।

### ২. ডোমেইন রেজিস্ট্রেশন ও এডিট ফর্ম (`/domains/new/`)
- ডোমেইনের নাম ইনপুট করার সময় বৈধ ডোমেইন সিনট্যাক্স ভ্যালিডেশন (`FQDN Validator`)।
- এক্সপায়ারি ডেট দেওয়ার সাথে সাথে জাভাস্ক্রিপ্ট দ্বারা স্বয়ংক্রিয়ভাবে কত দিন বাকি রয়েছে তা রিয়েল-টাইমে গণনা।
- কোম্পানি সিলেক্টর এবং অটো-রিনিউয়াল অন/অফ সুইচ।

---

## ৬. স্বয়ংক্রিয় নোটিফিকেশন ও অ্যালার্ট ইঞ্জিন (Automated Alert Engine)

সিস্টেমে একটি ম্যানেজমেন্ট কমান্ড বা ব্যাকগ্রাউন্ড টাস্ক অন্তর্ভুক্ত থাকবে (`send_domain_expiry_alerts`):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Daily Automated Cron Scan                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │   যাচাই: expiry_date <= today + 60, 30, 15, 7, 1 days?   │
       └────────────────────────────┬────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│       ইমেইল অ্যালার্ট         │               │     ড্যাশবোর্ড সিস্টেম নোটিশ   │
│ - আইটি হেড ও সিআইও-কে সতর্কবার্তা │               │ - ড্যাশবোর্ডে রেড/অ্যাম্বার ব্যানার │
│ - ডোমেইন নাম, রেজিস্ট্রার, বিলিং │               │ - অ্যাকশন প্ল্যান লিংক        │
└───────────────────────────────┘               └───────────────────────────────┘
```

---

## ৭. ধাপে ধাপে বাস্তবায়ন পরিকল্পনা (Implementation Roadmap)

| ধাপ | কাজ (Task) | আউটপুট ও ফাইলসমূহ |
| :---: | :--- | :--- |
| **Step 1** | **মডেল ও ডাটাবেজ আর্কিটেকচার** | `apps/domains/models.py` তৈরি, মাইগ্রেশন তৈরি ও রান। |
| **Step 2** | **ভিউ ও বিজনেস লজিক** | `apps/domains/views.py`: ডোমেইন লিস্ট, ফিল্টার, সেভ/আপডেট ও কেপিআই ক্যালকুলেশন। |
| **Step 3** | **ইউআরএল ও সাইডবার নেভিগেশন** | `apps/domains/urls.py`, গ্লোবাল `sidebar.html`-এ নতুন **"Domain & SSL Records"** মেন্যু আইটেম যোগ। |
| **Step 4** | **আধুনিক টেইলউইন্ড ইউআই টেমপ্লেট** | `templates/domains/domain_list.html` এবং `domain_form.html` তৈরি। |
| **Step 5** | **আকিজ গ্রুপের ডেমো সিড ডেটা** | `akij.net`, `akijplastics.com`, `akijcement.com`, `akij.com.bd` ইত্যাদি ডেমো ডোমেইন সিড করা। |
| **Step 6** | **টেস্ট সুইট ও কোয়ালিটি নিশ্চিতকরণ** | ইউনিট টেস্ট রান করা, কোড ভেরিফিকেশন এবং গিট কমিট (`git commit`) সম্পন্ন করা। |

---

## ৮. অনুমোদন ও পরবর্তী পদক্ষেপ (Sign-off & Next Steps)

এই পরিকল্পনাটি অনুমোদিত হলে সরাসরি **Step 1** থেকে কোডিং শুরু করা হবে।
