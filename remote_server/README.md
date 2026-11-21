# Akij Group - Central IT Asset Governance & Audit Portal
## Remote Server Turnkey Docker Deployment Package

এই ফোল্ডারটি (`remote_server/`) হলো একটি সম্পূর্ণ **স্ট্যান্ডঅ্যালন (Standalone) প্রোডাকশন ডেপ্লয়মেন্ট প্যাকেজ**। যেকোনো রিমোট VPS, ক্লাউড সার্ভার (AWS, DigitalOcean, Hetzner, Linode) বা অন-প্রেমিসেস ডেভিস/সার্ভারে কোনো সোর্স কোড বা পাইথন এনভায়রনমেন্ট ছাড়াই সরাসরি **Docker Hub** থেকে ইমেজ পুল করে এই পোর্টালটি ১ ক্লিকে রান করা যায়।

---

## 📦 আর্কিটেকচার ওভারভিউ

```
                    Internet / LAN
                          │
                          ▼
             [ Port 8000 / Port 80/443 ]
                          │
                          ▼
  ┌─────────────────────────────────────────────────────────┐
  │                 Docker Host (Any Linux Server)         │
  │                                                         │
  │   ┌─────────────────────────────────────────────────┐   │
  │   │ web Container (boniyeamin/ag-audit:production)  │   │
  │   │   - Django 5.2 Enterprise Core                  │   │
  │   │   - Gunicorn Multi-Worker HTTP Engine           │   │
  │   │   - Whitenoise Static Asset Serving             │   │
  │   └───────────────────────┬─────────────────────────┘   │
  │                           │ internal network            │
  │                           ▼                             │
  │   ┌─────────────────────────────────────────────────┐   │
  │   │ db Container (postgres:16-alpine)               │   │
  │   │   - Persistent Volume (postgres_data)           │   │
  │   │   - Automated Health Checks                     │   │
  │   └─────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────┘
```

- **Web Image:** `boniyeamin/ag-audit:production` (অথবা `:latest`)
- **Database Image:** `postgres:16-alpine`
- **Volume Persistence:** ডাটাবেজ এবং মিডিয়া ফাইল ভলিউমে সংরক্ষিত থাকে, কন্টেইনার আপডেট করলেও ডাটা মুছে যায় না।

---

## 🚀 রিমোট সার্ভারে ডেপ্লয়মেন্ট গাইড (Quick Start in 2 Minutes)

### পূর্বশর্ত (Prerequisites):
রিমোট সার্ভারে শুধুমাত্র **Docker** এবং **Docker Compose** ইনস্টল থাকতে হবে:
```bash
# Ubuntu/Debian-এ ডকার ইনস্টল না থাকলে:
curl -fsSL https://get.docker.com | sh
```

---

### ধাপ ১: রিমোট সার্ভারে ফোল্ডারটি পাঠানো
আপনার লোকাল মেশিন থেকে `remote_server` ফোল্ডারটি সার্ভারে কপি করুন:
```bash
# SCP দিয়ে রিমোট সার্ভারে পাঠানো:
scp -r remote_server/ user@your-server-ip:/opt/ag-audit
```
অথবা সার্ভারে SSH লগইন করে `/opt/ag-audit` এ ডিরেক্টরি তৈরি করুন।

---

### ধাপ ২: এক ক্লিকে ডেপ্লয়মেন্ট (`./deploy.sh`)
সার্ভারে ফোল্ডারে প্রবেশ করে ডিপ্লয় স্ক্রিপ্ট রান করুন:
```bash
cd /opt/ag-audit
chmod +x *.sh
./deploy.sh
```

**এই স্ক্রিপ্ট স্বয়ংক্রিয়ভাবে:**
1. `.env` ফাইল না থাকলে তৈরি করবে এবং স্বয়ংক্রিয়ভাবে শক্তিশালী ক্রিপ্টোগ্রাফিক `DJANGO_SECRET_KEY` ও `AUDIT_DB_PASSWORD` জেনারেট করবে।
2. Docker Hub থেকে সর্বশেষ `boniyeamin/ag-audit:production` ও `postgres:16-alpine` পুল করবে।
3. কন্টেইনার ব্যাকগ্রাউন্ডে চালু করবে এবং ডাটাবেজ মাইগ্রেশন (`migrate`) ও স্ট্যাটিক ফাইল (`collectstatic`) সম্পন্ন করবে।
4. হেলথ চেক ভেরিফাই করে সফল হলে লাইভ পোর্টাল URL প্রদর্শন করবে।

---

### ধাপ ৩: অ্যাডমিন অ্যাকাউন্ট (Superuser) তৈরি
সার্ভারে লগইন করার জন্য প্রথম অ্যাডমিন ইউজার তৈরি করুন:
```bash
docker compose exec web python manage.py createsuperuser
```
ইউজারনেম, ইমেইল এবং পাসওয়ার্ড দিন।

এখন ব্রাউজারে প্রবেশ করুন:
👉 **`http://<YOUR_SERVER_IP>:8000/`** (অথবা আপনার ডোমেইনে)

---

## ⚙️ কনফিগারেশন (`.env`)

প্রয়োজনীয় ভ্যারিয়েবল পরিবর্তন করতে `.env` ফাইল এডিট করুন:
```bash
nano .env
```

| ভ্যারিয়েবল | ডিফল্ট | বিবরণ |
|---|---|---|
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | আপনার সার্ভারের IP বা ডোমেইন (যেমন: `audit.akij.net,103.x.x.x`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:8000` | প্রটোকলসহ সম্পূর্ণ URL (যেমন: `https://audit.akij.net`) |
| `DJANGO_SECURE_SSL_REDIRECT` | `0` | SSL/HTTPS চালু থাকলে `1` করুন, HTTP হলে `0` রাখুন |
| `WEB_PORT` | `8000` | সার্ভারে যে পোর্টে পোর্টাল ওপেন থাকবে |
| `AUDIT_DB_NAME` | `ag_audit` | ডাটাবেজ নাম |
| `AUDIT_DB_USER` | `ag_audit` | ডাটাবেজ ইউজার |
| `AUDIT_DB_PASSWORD` | auto-generated | ডাটাবেজ পাসওয়ার্ড |

পরিবর্তন করার পর কন্টেইনার রিস্টার্ট করুন:
```bash
docker compose up -d
```

---

## 💾 ডাটাবেজ ব্যাকআপ ও রিস্টোর (Backup & Restore)

### ব্যাকআপ নেওয়া:
```bash
./backup.sh
```
এটি `./backups/` ফোল্ডারে টাইমস্ট্যাম্পসহ কমপ্রেসড ব্যাকআপ (`db_backup_ag_audit_YYYYMMDD_HHMMSS.sql.gz`) সংরক্ষণ করবে এবং ১৪ দিনের পুরোনো ব্যাকআপ স্বয়ংক্রিয়ভাবে মুছে ফেলবে।

### রিস্টোর করা:
```bash
./restore.sh ./backups/db_backup_ag_audit_20261121_210000.sql.gz
```

---

## 🛠️ প্রয়োজনীয় দৈনিক কমান্ডসমূহ (Cheatsheet)

```bash
# কন্টেইনারের রানিং স্ট্যাটাস দেখতে:
docker compose ps

# লাইভ অ্যাপ্লিকেশন লগ দেখতে:
docker compose logs -f web

# ডাটাবেজ লগ দেখতে:
docker compose logs -f db

# নতুন ইমেজ আপডেট করে রিস্টার্ট করতে:
./deploy.sh

# পোর্টাল বন্ধ করতে:
docker compose down

# ডাটাবেজ শেল প্রবেশ করতে:
docker compose exec db psql -U ag_audit -d ag_audit

# অ্যাপ কন্টেইনারে ব্যাশ টার্মিনাল ওপেন করতে:
docker compose exec web bash
```
