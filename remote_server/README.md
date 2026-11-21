# Akij Group - Central IT Asset Governance & Audit Portal
## Turnkey Remote Server Auto-Installer & Docker Deployment Package

এই ফোল্ডারটি (`remote_server/`) একটি সম্পূর্ণ **Zero-Touch Auto-Deployment Package**। যেকোনো নতুন বা বিদ্যমান রিমোট Linux VPS / ক্লাউড সার্ভারে (Ubuntu, Debian, CentOS, AlmaLinux, Rocky, Fedora, Kali, Alpine) শুধু এই ফোল্ডারটি দিয়ে `./deploy.sh` চালালে:
1. **OS Detect & Docker Install:** সার্ভারের অপারেটিং সিস্টেম স্বয়ংক্রিয়ভাবে ডিটেক্ট করবে এবং ডকার না থাকলে ডকার ইঞ্জিন ও কম্পোজ অটো ইনস্টল করে নিবে।
2. **Auto Server IP & Allowed Hosts:** সার্ভারের পাবলিক/লোকাল আইপি স্বয়ংক্রিয়ভাবে নির্ণয় করে কনফিগারেশনে বসিয়ে দেবে।
3. **Pulls from Docker Hub:** কোনো সোর্স কোড বা বিল্ড ছাড়া সরাসরি **Docker Hub (`boniyeamin/ag-audit:production` ও `postgres:16-alpine`)** থেকে ইমেজ নামিয়ে রান করবে।
4. **Auto Super Admin Creation:** স্বয়ংক্রিয়ভাবে ডাটাবেজ মাইগ্রেট করে সুপার অ্যাডমিন অ্যাকাউন্ট তৈরি করবে।
5. **Prints Ready Access URL & Credentials:** স্ক্রিনে সরাসরি ক্লিকযোগ্য লগইন ইউআরএল, ইউজারনেম ও পাসওয়ার্ড প্রদর্শন করবে।

---

## 🚀 এক কমান্ডে ডেপ্লয়মেন্ট (1-Command Quick Deploy)

### ধাপ ১: সার্ভারে ফোল্ডারটি পাঠানো
আপনার লোকাল মেশিন থেকে `remote_server/` ডিরেক্টরিটি সার্ভারে পাঠান:
```bash
scp -r remote_server/ user@your-server-ip:/opt/ag-audit
```

---

### ধাপ ২: ইনস্টলার রান করা
রিমোট সার্ভারে SSH দিয়ে লগইন করে স্ক্রিপ্টটি রান করুন:
```bash
cd /opt/ag-audit
chmod +x deploy.sh
./deploy.sh
```

স্ক্রিপ্টটি সম্পন্ন হলে টার্মিনালে ঠিক এরকম একটি ব্যানার দেখতে পাবেন:

```text
======================================================================
  🎉 AKIJ GROUP IT AUDIT PORTAL DEPLOYED SUCCESSFULLY!
======================================================================

  🌐 Portal Access URL:      http://103.x.x.x:8000/
  👤 Super Admin Username:  admin
  🔑 Super Admin Password:  Akij@e4a9!
  📧 Admin Email:           admin@akij.net

  📌 Quick Navigation Links:
     • Super Admin Hub:    http://103.x.x.x:8000/admin/super/dashboard/
     • Executive Reports:  http://103.x.x.x:8000/reports/
     • Asset Inventory:    http://103.x.x.x:8000/assets/

======================================================================
```

ব্রাউজারে সরাসরি **`http://<SERVER_IP>:8000/`** ওপেন করে প্রদত্ত ইউজারনেম ও পাসওয়ার্ড দিয়ে লগইন করুন!

---

## 📁 প্যাকেজ ফাইল ও গঠন

```
remote_server/
├── docker-compose.yml     # প্রোডাকশন কম্পোজ সার্ভিস (Web + PostgreSQL + optional Nginx)
├── .env.example           # কনফিগারেশন টেমপ্লেট
├── deploy.sh              # সম্পূর্ণ অটো-ইনস্টলার স্ক্রিপ্ট (OS Detection, Docker Setup, Admin Setup)
├── backup.sh              # অটোমেটিক PostgreSQL ডাটাবেজ ব্যাকআপ স্ক্রিপ্ট
├── restore.sh             # ব্যাকআপ ফাইল রিস্টোর স্ক্রিপ্ট
├── nginx/
│   └── nginx.conf         # অপশনাল রিভার্স প্রক্সি কনফিগারেশন
└── README.md              # এই নির্দেশিকা
```

---

## ⚙️ কাস্টমাইজেশন (`.env`)

যদি আপনি নিজস্ব অ্যাডমিন পাসওয়ার্ড বা ডোমেইন নাম ব্যবহার করতে চান, তবে `.env` ফাইলে এডিট করুন:
```bash
nano .env
```
- `ADMIN_USERNAME=myadmin`
- `ADMIN_PASSWORD=MyCustomStrongPassword123!`
- `DJANGO_ALLOWED_HOSTS=audit.mycompany.com,103.x.x.x`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://audit.mycompany.com,http://103.x.x.x:8000`
- `WEB_PORT=8000` (প্রয়োজনে পোর্ট পরিবর্তন করতে পারেন)

পরিবর্তন করার পর `./deploy.sh` পুনরায় রান করুন।

---

## 💾 ডাটাবেজ ব্যাকআপ ও রিস্টোর

### ব্যাকআপ তৈরি:
```bash
./backup.sh
```
কম্প্রেসড ব্যাকআপ ফাইল `./backups/db_backup_ag_audit_YYYYMMDD_HHMMSS.sql.gz` এ সংরক্ষিত হবে।

### ব্যাকআপ রিস্টোর:
```bash
./restore.sh ./backups/db_backup_ag_audit_20261121_210000.sql.gz
```

---

## 🛠️ দৈনিক ব্যবস্থাপনা কমান্ডসমূহ

```bash
# সব সার্ভিসের স্ট্যাটাস চেক:
docker compose ps

# লাইভ অ্যাপ্লিকেশন লগ দেখতে:
docker compose logs -f web

# ডাটাবেজ লগ দেখতে:
docker compose logs -f db

# পোর্টাল রিস্টার্ট করতে:
docker compose restart

# পোর্টাল সম্পূর্ণ বন্ধ করতে:
docker compose down

# নতুন সুপার অ্যাডমিন তৈরি করতে:
docker compose exec web python manage.py createsuperuser
```
