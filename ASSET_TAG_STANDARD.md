# Enterprise IT Asset Tag Standard Specification
**Akij Group IT Infrastructure & Asset Governance Standard**  
*Document Version: 2.0 | Status: Approved Standard | Scope: Group-wide*

---

## 1. Executive Summary & Overview

To maintain scalable, automated, and audit-compliant IT governance across **5,000 to 20,000+ assets** across all Akij Group business units, depots, and factories, this standard establishes a unified, human-readable, and machine-scannable **Asset Tag Format**:

$$\mathbf{\text{COMPANY}\ -\ \text{CATEGORY}\ -\ \text{SERIAL}}$$

### Recommended Standard Format
# **`APL-ROU-10001`**

```
┌─────────────┐   ┌─────────────┐   ┌─────────────────────────────┐
│     APL     │ - │     ROU     │ - │            10001            │
└──────┬──────┘   └──────┬──────┘   └──────────────┬──────────────┘
       │                 │                         │
  Company Code    Device Category         Unique Serial Sequence
 (Akij Plastics)     (Router)              (5-Digit Incremental)
```

### Key Advantages:
1. **Concise & Readable:** Compact length (13–15 characters) prints cleanly on standard $50\text{mm} \times 25\text{mm}$ asset label stickers and barcodes.
2. **Instant Identification:** Engineers and auditors immediately know the owning company and equipment category upon visual inspection.
3. **Decoupled from Physical Location:** Equipment frequently moves across branches, factories, and desks without requiring label re-printing or re-tagging.
4. **Massive Capacity:** Supports up to **90,000 unique assets per category per company** (10001 to 99999), expandable to 6 digits if needed.

---

## 2. Standard Device Category Codes

Standardized 2 to 4-letter category acronyms used across all physical hardware and virtual/logical assets:

| # | Device / Asset Category | Category Code | Physical / Logical | Example Asset Tag | Common Models / Description |
|---|------------------------|:-------------:|:------------------:|:-----------------:|-----------------------------|
| 1 | **Router** | `ROU` | Physical | `APL-ROU-10001` | MikroTik CCR1009, Cisco ISR 4331, EdgeRouter |
| 2 | **Switch** | `SWT` | Physical | `APL-SWT-10001` | Cisco Catalyst 2960X, Aruba 2530, TP-Link JetStream |
| 3 | **Firewall / Security** | `FWL` | Physical / Logical | `APL-FWL-10001` | Fortinet FortiGate 100F, Sophos XG, pfSense |
| 4 | **Access Point (Wi-Fi)** | `AP` | Physical | `APL-AP-10001` | Ubiquiti UniFi AP-AC-Pro, Cisco Meraki, Aruba |
| 5 | **Server (Physical Rack/Tower)** | `SRV` | Physical | `APL-SRV-10001` | Dell PowerEdge R740, HP ProLiant DL380 |
| 6 | **Desktop PC / All-in-One** | `DSK` | Physical | `APL-DSK-10001` | HP ProDesk 400 G6, Dell OptiPlex 7090 |
| 7 | **Laptop / Notebook** | `LAP` | Physical | `APL-LAP-10001` | Dell Latitude 5430, Lenovo ThinkPad T14, HP EliteBook |
| 8 | **Printer / Scanner** | `PRT` | Physical | `APL-PRT-10001` | HP LaserJet Pro M404, Canon imageRUNNER, Zebra ZD230 |
| 9 | **Storage (SAN / DAS / Disk Array)** | `STR` | Physical | `APL-STR-10001` | Dell EMC Unity, Synology RackStation, HPE MSA |
| 10 | **CCTV / Surveillance / NVR** | `CCTV` | Physical | `APL-CCTV-10001` | Hikvision NVR, Dahua IP Dome, Monitoring Station |
| 11 | **UPS / IPS / Power Management** | `UPS` | Physical | `APL-UPS-10001` | APC Smart-UPS 3000VA, Eaton, Rahimafrooz IPS |
| 12 | **Monitor / Display Unit** | `MON` | Physical | `APL-MON-10001` | Dell 24-inch IPS, Samsung Commercial Display |
| 13 | **IP Phone / VoIP Gateway** | `IPP` | Physical | `APL-IPP-10001` | Grandstream GXP2170, Cisco IP Phone 7841 |
| 14 | **Network Attached Storage (NAS)** | `NAS` | Physical | `APL-NAS-10001` | QNAP TS-453D, Synology DS920+ |
| 15 | **Virtual Machine / Cloud VM** | `VM` | Logical | `APL-VM-10001` | VMware ESXi VM, Hyper-V, AWS EC2, Proxmox VE |
| 16 | **Software License (OS/App)** | `LIC` | Logical | `APL-LIC-10001` | Windows 11 Enterprise, Microsoft 365 E5, Adobe CC |
| 17 | **Enterprise ERP User License** | `ERP` | Logical | `APL-ERP-10001` | SAP S/4HANA Named User, Oracle ERP Cloud |
| 18 | **SSL / TLS Certificate** | `SSL` | Logical | `APL-SSL-10001` | DigiCert Wildcard SSL, GlobalSign, Let's Encrypt |
| 19 | **Cloud Instance / Database** | `CLD` | Logical | `APL-CLD-10001` | AWS RDS PostgreSQL, Azure SQL Database |
| 20 | **Network Rack / Cabinet** | `RCK` | Physical | `APL-RCK-10001` | Toten 42U Server Rack, 9U Wallmount Rack |

---

## 3. Akij Group Company Code Directory

Company codes represent the legal business unit owning or financing the asset:

| Group Company | Code | Business Sector | Sample Asset Tag |
|---------------|:----:|-----------------|------------------|
| **Akij Plastics Ltd** | `APL` | Plastics, Household & Industrial | `APL-ROU-10001` |
| **Akij Motors / Match / Foods** | `AMFL` | Automotive, FMCG, Manufacturing | `AMFL-LAP-10001` |
| **Akij Jute Mills Ltd** | `AJML` | Textiles & Heavy Jute | `AJML-SWT-10001` |
| **Akij Ceramics / Cement** | `ACC` | Building Materials & Ceramics | `ACC-SRV-10001` |
| **Akij Food & Beverage Ltd** | `AFBL` | Food Processing & Beverages | `AFBL-PRT-10001` |
| **Akij Textile Mills Ltd** | `ATML` | Yarn Spinning & Textiles | `ATML-DSK-10001` |
| **Akij Shipping Lines Ltd** | `ASLL` | Marine Shipping & Logistics | `ASLL-FWL-10001` |
| **Akij Corporate / Headquarters** | `AKIJ` | Central Holding & Management | `AKIJ-SRV-10001` |

---

## 4. Architectural Decision: Why Location is Excluded from the Tag

### Alternative Format Considered:
`APL-HO-ROU-10001` *(Company - Location - Category - Serial)*

### Decision: **Exclude Location from Tag (`APL-ROU-10001`)**
1. **Dynamic Re-assignment without Relabeling:**
   - A laptop assigned to `LOC-001 (Head Office)` may be transferred next month to `LOC-002 (Chattak Factory)`. If `HO` was baked into the physical metallic barcode sticker, the physical label would become inaccurate or require scraping and re-tagging.
   - By keeping the tag location-neutral, the asset moves seamlessly while the database tracks location dynamically in real-time.
2. **Audit Accuracy:**
   - Physical audit scanners look up the asset tag. The audit app displays the expected location from the database and flags discrepancies (e.g., *"Asset APL-LAP-10042 scanned at Bogura Depot, but registered at Head Office"*).
3. **Short & Reliable Barcode Scanning:**
   - Fewer characters significantly improve barcode and 2D DataMatrix scanning read rates on small labels, reflective surfaces, and dark server racks.

> [!NOTE]
> If a specialized stationary facility strictly requires location codes in physical tags, the system supports enabling **Location Code in Tag** via System Settings (`asset_id_include_location = True`).

---

## 5. System Settings Configuration Specification

In the Administrator Portal under **System Settings $\rightarrow$ Asset ID Configuration**, the following parameters govern automatic generation:

| Setting Key | Label / Name | Default Value | Options / Scope | Purpose |
|-------------|--------------|:-------------:|-----------------|---------|
| `asset_id_prefix` | Asset ID Prefix | *(Empty)* | `AST`, `IT`, *(Empty)* | Optional global prefix. Leave blank for `APL-ROU-10001`. |
| `asset_id_include_company` | Include Company Code | `True` | `True` / `False` | Injects owning company short code (`APL`, `AMFL`, etc.). |
| `asset_id_include_category` | Include Category Code | `True` | `True` / `False` | Injects device type code (`ROU`, `SWT`, `LAP`, etc.). |
| `asset_id_include_location` | Include Location Code | `False` | `True` / `False` | Optional location code (`HO`, `FAC`, etc.). |
| `asset_id_start` | Starting Sequence Number | `10001` | `10001` – `99999` | Starting serial integer. Guarantees 5-digit consistency. |
| `asset_id_length` | Number Length / Padding | `5` | `4` to `8` digits | Zero-pads numbers (e.g. `10001`, `10002`). |
| `asset_id_separator` | Delimiter Separator | `-` | `-`, `_`, `.` | Standard dash delimiter between tokens. |
| `auto_generate` | Auto Generation | `True` | Enabled | Automatically populates `asset_tag` on save. |
| `duplicate_prevention`| Duplicate Prevention | `True` | Enforced | DB-level unique constraint prevents collisions. |

---

## 6. Sequence Generation & Concurrency Guarantees

Asset tag allocation uses **database row locking** and **atomic transactions** to guarantee 100% collision-free tags even during simultaneous bulk imports or multi-user entries:

```python
with transaction.atomic():
    sequence, _ = AssetIdSequence.objects.select_for_update().get_or_create(pk=1)
    number = max(config['asset_id_start'], sequence.last_number + 1)
    
    parts = asset_tag_components(config, self.location, self.device_type.category, self.device_type)
    separator = config['asset_id_separator']
    length = config['asset_id_length']
    
    while True:
        candidate = separator.join([*parts, str(number).zfill(length)])
        if not Asset.objects.filter(asset_tag=candidate).exists():
            break
        number += 1
        
    sequence.last_number = number
    sequence.save(update_fields=['last_number'])
    self.asset_tag = candidate
```

### Concurrency & Integrity Rules:
1. **Global Uniqueness:** `Asset.asset_tag` has `unique=True` and a database index (`db_index=True`).
2. **Atomic Row Lock:** `select_for_update()` prevents race conditions when two audit officers register equipment concurrently.
3. **No Sequence Re-use:** Even if an asset is damaged, scrapped, or retired (`SCRAP`), its Asset Tag is **permanently retired** and never re-issued to a new device.

---

## 7. Physical Asset Labeling & Barcode Standard

For physical assets deployed across Akij Group locations:

1. **Label Dimensions:** $50\text{ mm} \times 25\text{ mm}$ (or $60\text{ mm} \times 30\text{ mm}$ for servers/racks).
2. **Material:** Tamper-evident matte silver polyester or destructible vinyl (heat and water resistant).
3. **Symbology:**
   - **Barcode:** Code 128 (high density, alphanumeric).
   - **2D QR Code:** Contains URL `http://localhost:9000/assets/?q=APL-ROU-10001` for instant mobile audit scanning.
4. **Visual Layout:**
   - Top line: `AKIJ GROUP - IT ASSET INVENTORY`
   - Center: Scannable 1D Barcode & 2D QR Code
   - Bottom line: `APL-ROU-10001` (bold monospace font)

---

## 8. Summary Table of Operations

| Operation | Standard Workflow |
|-----------|-------------------|
| **New Asset Registration** | Tag auto-generates as `APL-ROU-10001` based on chosen Company & Device Type. |
| **CSV Bulk Ingestion** | Leave `asset_tag` column empty in CSV to auto-generate sequentially; or provide pre-assigned tags. |
| **Asset Movement / Relocation** | Update `location_id` in database. Asset tag remains unchanged. |
| **Asset Retirement** | Change status to `SCRAP`. Asset tag is archived and never re-allocated. |
