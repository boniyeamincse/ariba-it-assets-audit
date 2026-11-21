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
1. **Concise & Readable:** Typical length (12–15 characters with the company codes in this document) prints cleanly on standard $50\text{mm} \times 25\text{mm}$ asset label stickers and barcodes.
2. **Instant Identification:** The tag records the company that issued it and the equipment classification at issuance.
3. **Decoupled from Physical Location:** Equipment frequently moves across branches, factories, and desks without requiring label re-printing or re-tagging.
4. **Massive Capacity:** The group-wide sequence has **89,999 allocations** from 10001 through 99999. Increase the padding before exhausting that range.

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

For new device types the catalogue suggests a code once. Review the suggestion or select a code before the first asset is tagged. `OTHR` means Other and identifies catalogue records that may need review. Renaming a device type preserves its saved code, which is locked once an asset is tagged.

---

## 3. Akij Group Company Code Directory

Company codes identify the legal business unit at issuance. The asset stores the owning company independently of its current location. Ownership can change under central administration while the original tag stays valid. The company-code directory requires a confirmed legal entity for each code.

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
   - Scanning a physical label opens the exact asset record and shows its current registered location. The scanner or audit workflow can compare that location with the physical site.
3. **Short & Reliable Barcode Scanning:**
   - Keeping the tag short leaves room for the identifier and scan symbol. Verify readability with the actual printer, label material, and scanner before bulk printing.

> [!NOTE]
> If a specialized stationary facility strictly requires location codes in physical tags, the system supports enabling **Location Code in Tag** via System Settings (`asset_id_include_location = True`).

---

## 5. System Settings Configuration Specification

In the Administrator Portal under **System Settings $\rightarrow$ Asset ID Configuration**, the following parameters govern automatic generation:

| Setting Key | Label / Name | Default Value | Options / Scope | Purpose |
|-------------|--------------|:-------------:|-----------------|---------|
| `asset_id_prefix` | Asset ID Prefix | *(Empty)* | `AST`, `IT`, *(Empty)* | Optional global prefix. Leave blank for `APL-ROU-10001`. |
| `asset_id_include_company` | Include Company Code | `True` | `True` / `False` | Injects owning company short code (`APL`, `AMFL`, etc.). |
| `asset_id_include_category` | Include Category Code | `True` | `True` / `False` | Reads the saved Tag Category Code for the device type (`ROU`, `SWT`, `LAP`, etc.). |
| `asset_id_include_location` | Include Location Code | `False` | `True` / `False` | Optional location code (`HO`, `FAC`, etc.). |
| `asset_id_start` | Starting Sequence Number | `10001` | Positive integer within the configured width | First eligible serial. The existing counter continues if it has already allocated a higher serial. |
| `asset_id_length` | Number Length / Padding | `5` | `4` to `8` digits | Zero-pads numbers (e.g. `10001`, `10002`). |
| `asset_id_separator` | Delimiter Separator | `-` | `-`, `_`, `.` | Standard dash delimiter between tokens. |
| Auto generation | Blank manual tag | Enabled | The asset form and CSV generate a tag on save when no tag is supplied. |
| Duplicate prevention | Issued-tag registry | Enforced | Reserves issued tags, including retired tags. |

---

## 6. Sequence Generation & Concurrency Guarantees

The group uses a single monotonic sequence for automatically generated tags across every company and category. An atomic counter update acquires the database write lock before reading the allocated number. Allocation, tag reservation, and asset creation commit together.

1. **Global uniqueness.** The asset table enforces unique tags. A separate registry reserves issued tags case-insensitively and retains them independently of the asset row.
2. **Stable identity.** Moving the asset preserves the full tag. Device names, serial numbers from the manufacturer, and current locations are separate fields.
3. **Retirement.** The Retire action marks the asset as retired and keeps the record and identifier. Registration rejects duplicate manual tags and previously issued tags. CSV can update a current asset by exact tag when the operator enables updates.
4. **Existing data.** Existing tags remain valid without relabeling. The migration reserves current tags and legacy deletions identifiable in the activity log. Unrecorded historic tags must be reconciled with existing labels before a bulk rollout.
5. **Production database.** The application can run on PostgreSQL when `AUDIT_DB_ENGINE=postgresql` and the `AUDIT_DB_NAME`, `AUDIT_DB_USER`, `AUDIT_DB_PASSWORD`, `AUDIT_DB_HOST`, and `AUDIT_DB_PORT` settings are supplied. Verify simultaneous form and CSV registration against the production database engine before rollout.

---

## 7. Physical Asset Labeling & Barcode Standard

For physical assets deployed across Akij Group locations:

1. **Label Dimensions:** $50\text{ mm} \times 25\text{ mm}$ (or $60\text{ mm} \times 30\text{ mm}$ for servers/racks).
2. **Material:** Tamper-evident matte silver polyester or destructible vinyl (heat and water resistant).
3. **Symbology:**
   - **Barcode:** Code 128 is the proposed printed 1D format. The current label page provides QR printing. Validate any 1D output with the chosen printer software.
   - **2D QR Code:** Uses the HTTPS Application URL from General Settings and the exact `/assets/<id>/` route. The asset opens after sign-in with the user’s existing location access.
4. **Visual Layout:**
   - Top line: `AKIJ GROUP - IT ASSET INVENTORY`
   - Centre: Scannable QR code with sufficient clear space around the symbol
   - Bottom line: `APL-ROU-10001` (bold monospace font)

---

## 8. Summary Table of Operations

| Operation | Standard Workflow |
|-----------|-------------------|
| **New Asset Registration** | Tag auto-generates as `APL-ROU-10001` based on chosen Company & Device Type. |
| **CSV Bulk Ingestion** | Leave `asset_tag` column empty in CSV to auto-generate sequentially; or provide pre-assigned tags. Use optional `owning_company_code` when ownership differs from the selected location’s company. |
| **Asset Movement / Relocation** | Update `location_id` in database. Asset tag remains unchanged. |
| **Asset Retirement** | Use Retire asset. The record is marked retired, retains its tag, and stays available for audit history. |
