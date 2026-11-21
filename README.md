# Akij IT Asset Audit & Multi-Location Inventory System

Enterprise web application built with **Python Django + Django Templates (HTML5 / TailwindCSS)** designed to audit and track IT devices across **Head Office, Factories, and Depots**.

---

## 🚀 Quick Start (কীভাবে চালাবেন)

প্রজেক্ট ফোল্ডারে টার্মিনাল খুলে নিচের কমান্ডটি রান করুন:

```bash
python3 manage.py runserver 9000
```

এরপর যেকোনো ব্রাউজারে যান:
👉 **[http://localhost:9000/](http://localhost:9000/)**

* **Login URL:** [http://localhost:9000/login/](http://localhost:9000/login/)
* **Django Admin Panel:** [http://localhost:9000/admin/](http://localhost:9000/admin/)

---

### 🔐 Role-Based Demo / Test Accounts (টেস্ট ইউজার ও পাসওয়ার্ড টেবিল)

সিস্টেমে **Corporate Email** অথবা **Username**—উভয় মাধ্যমেই লগইন সাপোর্ট করে:

| Role (ভূমিকা) | Corporate Email | Username | Password | Location Scope | Dashboard & Permissions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Super Admin**<br>*(CIO / Head of IT)* | `admin@akij.net` | `admin` | `admin123` | **All Locations**<br>(Group-Wide) | Full System Administration, Security Policies, User RBAC & Audits |
| **HO Admin**<br>*(Lead Central Auditor)* | `auditor@akij.net` | `auditor` | `audit123` | **All Locations**<br>(HO + Factories + Depots) | Asset Master Registry, 39 Software Categories, SLM Compliance Hub |
| **HO Admin**<br>*(Management / Sir)* | `director@akij.net` | `sir` | `sir123` | **All Locations**<br>(Executive View) | Executive High-Level Analytics, Location Matrix, Excel & PDF Print |
| **Factory Admin**<br>*(Factory IT In-Charge)* | `factory@akij.net` | `factory_admin` | `factory123` | **APL Factory Chattak**<br>(Assigned Factory) | Local Physical Device Audit, Stock Reconciliation & Tagging |
| **Depot Admin**<br>*(Regional IT Executive)* | `depot@akij.net` | `depot_admin` | `depot123` | **Bogura & Chattogram**<br>(Assigned Depots) | Regional Depot Inventory Verification, Spares & Dispatch Tracking |

> 💡 **টেস্ট ইউজার রিসেট / সিড কমান্ড:**
> যে কোনো সময় টেস্ট ইউজারগুলো পুনরায় তৈরি করতে টার্মিনালে রান করুন:
> ```bash
> python3 manage.py seed_test_users
> ```

---

## 🏢 মডিউল ও ফোল্ডার আর্কিটেকচার (Future-Proof Modular Design)

ভবিষ্যতে যেন যেকোনো নতুন ফিচার (যেমন: বারকোড/QR ট্র্যাকিং, অ্যাসেট ট্রান্সফার গেটপাস, ওয়ারেন্টি রিপেয়ার) খুব সহজে যুক্ত করা যায়, সেভাবে অ্যাপগুলোকে মডুলার আর্কিটেকচারে ভাগ করা হয়েছে:

```
audit/
├── manage.py
├── core_project/           # Django settings, root URLs, WSGI
├── apps/
│   ├── common/            # Base TimeStampedModel, Activity Logging
│   ├── locations/         # Head Office, Factories (Chattak), Depots
│   ├── devices/           # Master Catalog (Infrastructure & User Devices)
│   ├── audits/            # Physical Stock Count Engine & JSON Sync
│   └── reports/           # Executive Dashboard, Charts, PDF & Excel Export
├── templates/             # Modern HTML5 + Tailwind CSS UI
│   ├── base.html          # Enterprise layout with sidebar & topbar
│   ├── dashboard.html     # Real-time Executive Dashboard for Sir
│   ├── reports/
│   │   └── matrix.html    # All-Locations Comparison Matrix
│   └── audits/
│       ├── audit_list.html
│       ├── audit_detail.html
│       ├── audit_form.html    # Fast data entry with live JS auto-calc
│       ├── audit_print.html   # Official A4 Print/PDF with 3 signatures
│       └── sync_json.html     # Offline JSON backup and upload
└── docs/
    └── SOFTWARE_SPECIFICATION.md # পূর্ণাঙ্গ সিস্টেম স্পেসিফিকেশন
```

---

## 📊 সিস্টেমে অন্তর্ভুক্ত সুবিধাসমূহ

1. **Executive Dashboard for Sir:**
   - প্রতিষ্ঠানে মোট ডিভাইস সংখ্যা (Total IT Assets), সচল (Active), ব্যাকআপ (Backup) এবং নষ্ট (Faulty) ডিভাইসের অনুপাত।
   - **Chart.js** দ্বারা তৈরি লাইভ ক্যাটাগরি ডোনাট চার্ট এবং টপ ডিভাইসের বার চার্ট।
2. **Multi-Location Comparison Matrix (`/matrix/`):**
   - Head Office, Chattak Factory, Bogura Depot, Chattogram Depot—সব লোকেশন ও ডিভাইসের তুলনামূলক ক্রস-ট্যাব টেবিল।
   - **Download Excel (.xlsx):** এক ক্লিকে সম্পূর্ণ ম্যাট্রিক্স এক্সেল ফাইলে ডাউনলোড।
3. **ছাতক ফ্যাক্টরির রেডিমেড ডেটা (APL Factory Chattak):**
   - আপনার দেওয়া ছবি দুটি থেকে হুবহু **৪৫৯টি ডিভাইসের ডেটা** (Infrastructure: ২০৯টি, Users: ২৫০টি) অলরেডি সিস্টেমে ডাটাবেজ সহ এন্ট্রি করা আছে।
4. **অফিশিয়াল প্রিন্ট ও PDF রিপোর্ট (`/audits/1/print/`):**
   - Akij Plastics Ltd-এর অফিশিয়াল হেডার ও প্যাড।
   - অডিটর (Prepared By), ফ্যাক্টরি ইন-চার্জ (Verified By) এবং ম্যানেজমেন্ট / স্যারের (Approved By) সিল-স্বাক্ষরের নির্ধারিত স্থান।
5. **অফলাইন JSON সিঙ্ক (`/sync-json/`):**
   - প্রত্যন্ত ডিপো বা ফ্যাক্টরিতে ইন্টারনেট ছাড়া ল্যাপটপে অফলাইনে ডেটা এন্ট্রি নিয়ে `.json` ফাইল এক্সপোর্ট/ইমপোর্ট করার সুবিধা।
6. **সিস্টেম অ্যাক্টিভিটি ও অডিট লগ পেজ (`/logs/`):**
   - কে কখন লগইন করেছে, কোন ইউজার কোন ফ্যাক্টরির কাউন্ট আপডেট বা সেভ করেছে, তার সম্পূর্ণ টাইমস্ট্যাম্পযুক্ত অডিট ট্রেইল (IP অ্যাড্রেস ও ইউজারনেম সহ)।
   - মডিউল, অ্যাকশন টাইপ এবং কিওয়ার্ড দিয়ে সরাসরি ফিল্টার করার ব্যবস্থা।

---

## 🔮 ভবিষ্যতে নতুন ফিচার যোগ করার পদ্ধতি (Future Extensions)

* **Individual Serial Number / QR Code Tracking:** শুধুমাত্র `apps/assets/` বা `apps/tags/` তৈরি করে `DeviceType`-এর সাথে ফরেন কী লিঙ্ক করলেই প্রতি পিসি বা সুইচের সিরিয়াল ট্র্যাক করা যাবে।
* **Inter-Location Transfer & Gate Pass:** এক সাইট থেকে অন্য সাইটে ডিভাইস পাঠাতে `apps/transfers/` মডিউল অ্যাড করলেই চালান ও গেটপাস তৈরি হবে।
* **Warranty & Servicing:** সার্ভিসিং ট্র্যাকিংয়ের জন্য `apps/maintenance/` যোগ করা যাবে।
