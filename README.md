# Akij Group IT Asset Audit & Multi-Location Inventory System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2.x-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-CDN-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Database](https://img.shields.io/badge/Database-SQLite3%20%7C%20PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Developed By](https://img.shields.io/badge/Developed%20By-Ariba%20Soft-2563EB)](https://github.com/boniyeamincse/ariba-it-assets-audit)

An enterprise-grade IT Asset Governance, Audit & Inventory Management platform tailored for large-scale conglomerates, manufacturing plants, regional depots, and central corporate offices.

Built with **Python 3**, **Django 5.2**, and a modern **Tailwind CSS + Chart.js** interface, this platform centralizes physical hardware tracking, multi-stage physical stock audit workflows, software license compliance, domain/SSL lifecycle monitoring, and role-based access governance.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start (Local Development)](#-quick-start-local-development)
- [Demo / Test User Credentials](#-demo--test-user-credentials)
- [Asset ID Standard & QR Code Engine](#-asset-id-standard--qr-code-engine)
- [Audit & Reconciliation Workflow](#-audit--reconciliation-workflow)
- [Central System Administration](#-central-system-administration)
- [Automated Scheduled Tasks](#-automated-scheduled-tasks)
- [Production Deployment (Docker Turnkey)](#-production-deployment-docker-turnkey)
- [Contributing & Code Standards](#-contributing--code-standards)
- [Credits & Maintenance](#-credits--maintenance)

---

## ✨ Key Features

### 🏢 1. Multi-Location Asset Inventory Management
- **Hierarchical Site Structure:** Manage inventory across Head Office (HO), Manufacturing Factories (e.g. Chattak), Regional Depots (Bogura, Chattogram), Warehouses, and Branches.
- **Hardware Catalog:** Two-tier classification consisting of Hardware Categories (Infrastructure, End-User, Logical/Cloud) and Device Sub-Types (Laptops, Servers, Routers, Switches, CCTV, etc.).
- **Live Status & Conditions:** Track assets in real-time across four core states: *Working / In-Use*, *Backup / Spare*, *Faulty / Repair*, and *Damaged / Scrap*.
- **Bulk Import:** High-performance CSV import engine for rapid inventory onboarding with format validation.

### 🏷️ 2. Enterprise Asset ID Standard & QR Printing
- **Structured Asset Tagging:** Configurable asset numbering standard following the pattern `[PREFIX]-[COMPANY]-[LOCATION]-[CATEGORY]-[SEQUENCE]` (e.g. `APL-ROU-10001` or `AST-AMFL-HO-NET-00001`).
- **Dynamic QR Code Generator:** Automatic QR generation containing device specifications, serial numbers, and direct portal verification URLs.
- **Printable Labels:** Ready-to-print industrial asset label stickers formatted for barcode/thermal label printers.

### 📋 3. Physical Stock Audit & Verification Workflow
- **Multi-Stage Lifecycle Governance:**
  $$\text{Draft} \longrightarrow \text{Submitted} \longrightarrow \text{In Review} \longrightarrow \text{Verified} \longrightarrow \text{Approved / Rejected}$$
- **Discrepancy Calculation:** Live computation of Expected vs. Counted vs. Surplus/Shortage physical quantities.
- **Official 3-Signature Printable Certificate (`/audits/<id>/print/`):** Formatted for A4 printing with designated stamp and signature zones for:
  1. *Prepared By (Site Auditor)*
  2. *Verified By (Factory / Depot IT In-Charge)*
  3. *Approved By (Chief Information Officer / Central Management)*

### 📊 4. Executive Analytics & Cross-Location Matrix
- **Executive Dashboard:** Live KPI cards, asset health distribution, warranty status, and Chart.js category breakdown donuts.
- **Cross-Location Comparison Matrix (`/matrix/`):** Pivot-style inventory comparison table showing device counts across all physical sites.
- **1-Click Excel Export:** Instant high-speed `.xlsx` export of the entire inventory matrix using `openpyxl`.

### 🔑 5. Software & License Management (SLM)
- **39 Software Categories:** Categorized catalog covering Operating Systems, Office Suites, ERP/SAP Seats, Engineering (CAD), Cybersecurity/Endpoint, and Cloud Subscriptions.
- **Compliance Tracking:** Real-time license allocation, license key masking, seat consumption, and expiry date alerts.

### 🌐 6. Corporate Domain, DNS & SSL Monitoring
- **Registrar Management:** Central registry for GoDaddy, BTCL, Cloudflare, Namecheap, and corporate DNS hosts.
- **SSL / TLS Expiry Countdown:** Automated calculation of days remaining with visual warning flags for domains/certificates expiring within 30 days.
- **DNS Records:** Centralized record of Primary/Secondary Nameservers, A Records, and Corporate Mail MX hosts.

### 🔒 7. Enterprise Security & Audit Trail
- **Role-Based Access Control (RBAC):** Strict permission boundary separation between Super Admin, HO Admin, Factory Admin, Depot Admin, and Custom Roles.
- **CIDR Network Restrictions:** IP allowlisting restricting administration actions to authorized company networks.
- **Brute-Force Protection:** Account lockout policies after consecutive failed password attempts.
- **Tamper-Evident Activity Log (`/admin/activity/`):** Every sign-in, permission modification, asset transfer, and system change is immutably timestamped with user identification and remote IP address.

---

## 🏛 System Architecture

The project follows a modular, decoupled architecture where each domain is encapsulated inside its own reusable Django app:

```
audit/
├── core_project/                   # Project configuration, URLs, WSGI/ASGI, base settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/                   # Authentication, user profiles, RBAC roles, navigation, admin views
│   ├── audits/                     # Physical count audits, workflow state engine, print certificates
│   ├── common/                     # SystemSettings, audit logs, preferences, middleware, base models
│   ├── devices/                    # Asset models, hardware categories, QR engine, CSV import
│   ├── domains/                    # Domain registration, DNS records, SSL expiry tracking
│   ├── locations/                  # Company entities, multi-location sites (HO, Factories, Depots)
│   └── reports/                    # Executive dashboard views, matrix analysis, Excel exports
├── templates/                      # Semantic HTML5 + Tailwind CSS UI templates
│   ├── accounts/                   # Login, user editors, role forms
│   ├── administration/             # Central 14-module System Settings portal
│   ├── audits/                     # Audit creation, review, and A4 print templates
│   ├── devices/                    # Asset list, forms, QR view, hardware catalog
│   ├── domains/                    # Domain list, registration, DNS view
│   ├── navigation/                 # Modern responsive sidebar, topbar, modals
│   └── reports/                    # Dashboard, matrix comparison view
├── static/                         # CSS styling (portal-shell, preferences), JS modules
├── docs/                           # Software specifications, asset standards, domain docs
├── remote_server/                  # Production turnkey Docker deployment, Nginx, backup scripts
├── manage.py                       # Django CLI entrypoint
├── requirements.txt                # Python package dependencies
└── start.sh                        # One-click startup script for port 9000
```

---

## 🛠 Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.11+ / Django 5.2 | High-performance MTV backend with atomic transactions |
| **Frontend Styling** | Tailwind CSS CDN | Modern utility-first responsive layout with dark/light mode |
| **UI Components** | FontAwesome 6 + Chart.js | Iconography, responsive analytics donut and bar charts |
| **Spreadsheets** | `openpyxl` | Native `.xlsx` parsing and dynamic matrix export engine |
| **QR Code Engine** | `qrcode` + PIL | On-the-fly QR code generation for physical asset labels |
| **Database** | SQLite3 (Dev) / PostgreSQL (Prod)| Zero-config dev database; PostgreSQL 16+ for production |
| **Production Server** | Gunicorn + Nginx + WhiteNoise| High-concurrency WSGI runner with static file caching |
| **Containerization**| Docker & Docker Compose | Multi-container production deployment package |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11, 3.12, or 3.14
- Git
- Virtual Environment tool (`venv`)

### 1. Clone the Repository
```bash
git clone git@github.com:boniyeamincse/ariba-it-assets-audit.git
cd ariba-it-assets-audit
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Seed Initial Demo Users & Master Data (Optional)
```bash
python manage.py seed_test_users
```

### 6. Run the Development Server
```bash
./start.sh
# Or alternatively:
python manage.py runserver 0.0.0.0:9000
```

Open your browser and navigate to:
- **Application Portal:** [http://localhost:9000/](http://localhost:9000/)
- **Sign In:** [http://localhost:9000/login/](http://localhost:9000/login/)
- **System Settings:** [http://localhost:9000/admin/settings/](http://localhost:9000/admin/settings/)
- **Technical Django Admin:** [http://localhost:9000/admin/](http://localhost:9000/admin/)

---

## 🔐 Demo / Test User Credentials

The system supports signing in via either **Username** or **Corporate Email**:

| Role | Username | Corporate Email | Password | Scope & Dashboard | Permissions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` | `admin@akij.net` | `admin123` | **All Locations** (Group-Wide) | Full System Control, 14-Module Settings, User RBAC & Audits |
| **HO Admin** | `auditor` | `auditor@akij.net` | `audit123` | **All Locations** (Central View) | Asset Master Registry, Software License Compliance Hub |
| **HO Admin** | `sir` | `director@akij.net` | `sir123` | **All Locations** (Executive View) | Executive Dashboard, Comparison Matrix, PDF/Excel Exports |
| **Factory Admin**| `factory_admin` | `factory@akij.net` | `factory123` | **Chattak Factory** | Local Asset Audits, Stock Reconciliation & QR Tagging |
| **Depot Admin** | `depot_admin` | `depot@akij.net` | `depot123` | **Bogura & Chattogram Depots** | Regional Inventory Verification, Standby Spares Tracking |

---

## 🏷️ Asset ID Standard & QR Code Engine

The asset ID engine guarantees unique, auditable identifiers across group companies:

$$\text{Asset Tag} = \text{Prefix} + \text{Company Code} + \text{Location Code} + \text{Category Code} + \text{Padded Number}$$

* **Example:** `APL-ROU-10001` (Akij Plastics Ltd $\rightarrow$ Router $\rightarrow$ Sequence `10001`)
* **Real-time Preview:** Configurable live in `/admin/settings/asset-id/` with instant AJAX feedback.
* **QR Codes:** Encodes device details and tag format directly into vector/PNG images for physical asset stickers.

---

## ⚙️ Central System Administration

Accessible at `/admin/settings/`, the administrative console features 14 modules:

| Module | Purpose & Managed Settings |
| :--- | :--- |
| **General Settings** | App Name, Short Name, Description, Landing Route, Global Maintenance Mode |
| **Organization Settings** | Group Name, Company Logo, Address, Default Company, Financial Year Start |
| **Appearance Settings** | Brand Colors (Primary/Secondary Hex), Logos, Favicon, Light/Dark/System Theme |
| **Asset Configuration** | Currency (BDT), Warranty Period, Conditions, Criticalities, Status Labels |
| **Asset ID Configuration**| Prefix, Separators, Sequential Length, Overrides, Real-time Preview |
| **Notification Settings** | Alert Triggers (Asset Creation, Expiry), Email Digests, Notification Frequency |
| **Email (SMTP)** | SMTP Host, Port (587/465), TLS/SSL Encription, Sender Email & Credentials |
| **Security Settings** | Minimum Password Length, Complexity Enforcement, Lockout Durations, IP Allowlist |
| **User & Access** | Self-Registration Policy, Default New Account Roles, Inactive Account Rules |
| **Backup Settings** | Automated Backup Schedules, Daily/Weekly Frequencies, Retention Policies |
| **Audit Log Settings** | Activity Log Pagination Size, Audit Event Retention Window |
| **Localization** | Timezone (`Asia/Dhaka`), Date/Time Formats (`DD-MM-YYYY`), Number Notation |
| **Integration Settings** | REST API Token Authentication, Akij ERP Sync Endpoints, LDAP / Active Directory |
| **System Maintenance** | Diagnostic Health Status, Vacuum Optimization, Admin Maintenance Bypass |

---

## ⏱️ Automated Scheduled Tasks

The platform provides built-in Django management commands for server crons:

```bash
# Send daily/weekly asset digest emails to configured recipients
python manage.py send_asset_digest

# Dispatch 30-day warranty expiration reminders
python manage.py send_warranty_alerts

# Execute automated database & media backups to external storage
python manage.py run_system_backup

# Prune activity logs according to retention policy
python manage.py prune_activity_logs --apply
```

---

## 🐳 Production Deployment (Docker Turnkey)

For production deployment, an automated turnkey package is provided in `remote_server/`:

```bash
cd remote_server

# 1. Configure production secrets
cp .env.example .env
nano .env

# 2. Run automated turnkey deploy script
chmod +x deploy.sh
sudo ./deploy.sh
```

The script automatically detects the host OS, provisions Docker Engine and Compose if absent, sets up a secure PostgreSQL database, runs migrations, collects static assets, configures Nginx reverse proxy with SSL, and starts Gunicorn.

---

## 🧪 Running Tests

Execute the complete automated test suite (including permission matrix, asset tag generation, system settings verification, and backup integration):

```bash
python manage.py test apps
```

---

## 👨‍💻 Credits & Maintenance

- **Developed By:** **Ariba Soft**
- **Repository:** [boniyeamincse/ariba-it-assets-audit](https://github.com/boniyeamincse/ariba-it-assets-audit)
- **Primary Developer / Maintainer:** [Boni Yeamin](https://github.com/boniyeamincse)
- **License:** Enterprise Proprietary &mdash; All Rights Reserved.
