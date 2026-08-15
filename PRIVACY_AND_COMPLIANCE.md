# Privacy Architecture & Regulatory Compliance

This document outlines the cryptographic privacy guarantees, data boundaries, and regulatory compliance standards embedded within **TRACE** (*Targeted Routing & Account Cluster Extraction*).

---

## 1. Zero-PII Privacy Architecture

TRACE is engineered with a strict mathematical privacy boundary designed to eliminate the cross-bank money mule blind spot without creating a centralized database of citizen financial records.

```
       +-------------------------------------------------------------+
       |                  CENTRAL INTELLIGENCE NETWORK               |
       |                (Flow A & Flow B Traversal Engine)           |
       |                                                             |
       |  - Cryptographic Standing Hashes (HMAC-SHA256)              |
       |  - Ephemeral Investigation Salts (24-hour Auto-Purge)       |
       |  - Zero Customer Names, Account Numbers, or PANs            |
       +------------------------------+------------------------------+
                                      |
                           Strict Privacy Boundary
             (No PII passes outward - Only cryptographic identifiers)
                                      |
       +------------------------------+------------------------------+
       |             LOCAL PARTICIPATING BANK NODE (e.g. SBI)        |
       |                                                             |
       |  [Airgapped Bank Vault]                                     |
       |  - Private Customer PII (Rajesh Kumar, A/C 40991209384)     |
       |  - Local Core Banking System (CBS) Ledger                   |
       |  - De-anonymizes incoming alert matches locally             |
       |  - Direct STR Filing to FIU-IND Gateway                     |
       +-------------------------------------------------------------+
```

---

## 2. Dual Hashing Architecture: Standing vs. Ephemeral

| Feature | Standing Hash (Flow A) | Ephemeral Hash (Flow B) |
|---|---|---|
| **Cryptographic Primitive** | HMAC-SHA256 | HKDF + Session Salt |
| **Key Management** | Global Key rotated every 30 days | Per-Investigation Salt (generated per query) |
| **Persistence** | Graph node representation | In-memory only; **destroyed upon investigation close** |
| **Purpose** | Continuous multi-bank cluster matching | Bounded graph expansion & forensic trace |
| **Linkability** | Linkable within 30-day window | Unlinkable across investigations |

---

## 3. Data Flow & Boundary Specification

### What Data Moves Centrally:
- Pseudonymized standing hashes (`HMAC:...`)
- Inter-bank transaction timestamps & amounts
- Obfuscated feature vectors (pass-through ratios, velocities, in/out degrees)
- Aggregated subgraph component IDs

### What Data NEVER Leaves the Bank:
- Customer Full Name
- Real Account Numbers & IFSC codes
- Permanent Account Number (PAN) / Aadhaar / National ID
- Contact details (Phone, Email, Physical Address)
- Local credit history & KYC documents

---

## 4. Statutory & Regulatory Compliance

TRACE is built to comply with Indian and international financial intelligence frameworks:

### 1. Section 12, Prevention of Money Laundering Act (PMLA) 2002
- Banks are legally mandated to furnish information on suspicious transactions to the **Financial Intelligence Unit (FIU-IND)** within 7 days of suspicion.
- TRACE accelerates detection from **days/weeks to sub-second automated STR generation**.

### 2. Reserve Bank of India (RBI) Cyber Security Framework
- Mandates multi-institution fraud detection while preserving customer data confidentiality.
- TRACE's zero-PII design complies directly with RBI guidelines on third-party data processing and cloud computing.

### 3. Digital Personal Data Protection Act (DPDPA) 2023
- Enforces purpose limitation, data minimization, and storage limitation.
- TRACE's ephemeral key deletion ensures that temporary investigation identifiers cannot be repurposed or retroactively unmasked.

---

## 5. Threat Modeling & Residual Risk Mitigations

| Threat Vector | Potential Impact | TRACE Mitigation |
|---|---|---|
| **Rainbow Table / Precomputation Attack** | Attacker hashes known account numbers to reverse standing hashes. | HMAC uses a 256-bit secret key managed via HSM; dictionary attacks without the key yield 0 matching entropy. |
| **Key Compromise** | Exposure of standing key allows historical linking. | Key rotation every 30 days; all Flow B investigations use disposable ephemeral salts that are permanently deleted upon completion. |
| **Traffic / Graph Analysis** | Attacker infers identity from transaction amounts. | Feature extraction operates on normalized graph metrics; individual transaction amounts are aggregated into component feature vectors. |
| **Malicious Bank Node Query** | Rogue bank node attempts arbitrary graph discovery. | Pattern decay limits traversal depth; rate limiting and audit logging track every query. |
