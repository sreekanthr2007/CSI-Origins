# TRACE: Targeted Routing & Account Cluster Extraction
### *Cross-Bank Mule Account Detection Network with Zero-PII Cryptographic Privacy*

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/)
[![Tests](https://img.shields.io/badge/tests-141%20passing%20%28100%25%29-success.svg)](https://github.com/)
[![Compliance](https://img.shields.io/badge/compliance-PMLA%20Sec%2012%20%7C%20FIU--IND-blue.svg)](https://github.com/)
[![Privacy](https://img.shields.io/badge/privacy-Zero--PII%20Guaranteed-orange.svg)](https://github.com/)

---

## 1. Project Overview

**TRACE** is a next-generation, privacy-preserving financial intelligence platform designed to eliminate the cross-bank money mule blind spot. 

By leveraging **cryptographic standing hashes (HMAC-SHA256)**, **ephemeral investigation salts**, **temporal graph traversal**, and **ensemble machine learning with SHAP explainability**, TRACE detects multi-bank money laundering networks in milliseconds while guaranteeing that citizen Personally Identifiable Information (PII) never leaves individual bank vaults.

---

## 2. Architecture & Privacy Boundary

```
+-----------------------------------------------------------------------------------+
|                        CENTRAL INTELLIGENCE LAYER (Zero PII)                      |
|                                                                                   |
|  [Flow A: Continuous Monitoring]          [Flow B: Targeted Forensic Traversal]   |
|  - Temporal Graph Engine                  - Bounded Pattern-Decay Search          |
|  - 29 Topological Graph Features          - Ephemeral Salt Management (24h)       |
|  - XGBoost + RF Hybrid Ensemble           - Interactive Forensic Playback Trace   |
|  - SHAP Attribution Decomposition         - Multi-Bank Alert Dispatcher           |
+------------------------------------------+----------------------------------------+
                                           |
                              STRICT PRIVACY BOUNDARY
              (Only HMAC tokens & graph metadata pass across boundary)
                                           |
+------------------------------------------+----------------------------------------+
|                      PARTICIPATING BANK NODES (Airgapped)                         |
|                                                                                   |
|  [Bank SBI Node]            [Bank HDFC Node]            [Bank ICICI Node]         |
|  - Private Customer Vault   - Private Customer Vault    - Private Customer Vault  |
|  - Local De-Anonymization   - Local De-Anonymization    - Local De-Anonymization  |
|  - Freeze / Lien Execution  - Freeze / Lien Execution   - Freeze / Lien Execution |
|  - Section 12 PMLA STR      - Section 12 PMLA STR       - Section 12 PMLA STR     |
|    Filing to FIU-IND          Filing to FIU-IND           Filing to FIU-IND       |
+-----------------------------------------------------------------------------------+
```

---

## 3. Technology Stack

- **Backend**: Python 3.11, FastAPI, NetworkX, XGBoost, Scikit-Learn, SHAP, SQLite3, Pydantic
- **Frontend**: React 18, TypeScript, TailwindCSS v4, React Flow (@xyflow/react), Lucide Icons, Vite
- **Containerization & Deployment**: Docker (Multi-stage builds), Docker Compose, Nginx Reverse Proxy
- **Testing**: Pytest, FastAPI TestClient, 141 Automated Unit, Integration, Benchmark & E2E Suites

---

## 4. Quick Start & Local Setup

### Option A: Running with Docker Compose (Recommended)
```bash
# Build and start all services in detached mode
docker-compose up -d --build

# Open browser to Central Intelligence Dashboard
# http://localhost/central
```

### Option B: Running Locally from Source

#### 1. Backend Setup:
```bash
# Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend ASGI server on port 8000
uvicorn backend.app.main:app --reload --port 8000
```

#### 2. Frontend Setup:
```bash
cd frontend
npm install
npm run dev
# Dashboard opens on http://localhost:5173
```

---

## 5. Running the Interactive Demo & Test Suites

### Run All 141 Automated Tests:
```bash
python -m pytest
```

### Run Interactive Multi-Scenario CLI Demo:
```bash
python backend/scripts/demo_e2e.py --all
```
*Generates an interactive summary and writes [`demo_report.html`](file:///c:/Users/HP/Desktop/CSI%20origins/demo_report.html).*

---

## 6. Pre-Packaged Demo Scenarios

| Scenario | Pattern Topology | Volume & Velocity | Flow A Result | STR Action |
|---|---|---|---|---|
| **Scenario 1** | Fast 4-Bank Rapid Chain (`SBI -> HDFC -> ICICI -> AXIS`) | ₹5,00,000 in 42 minutes | **$p=0.92$ (Mule Detected)** | Filed to FIU-IND |
| **Scenario 2** | Collector Star Motif (8 senders fanning into 1 hub) | ₹3,84,000 in 18 minutes | **$p=0.82$ (Mule Detected)** | Filed to FIU-IND |
| **Scenario 3** | Smurfing Ring (1 hub $\rightarrow$ 10 structured transfers) | ₹4,95,000 ($10 \times ₹49,500$) | **$p=0.92$ (Mule Detected)** | Filed to FIU-IND |
| **Scenario 4** | Legitimate Account Hold Decay (Salary disbursement) | 3-day hold, commercial pattern | **$p=0.02$ (Legitimate)** | Traversal Halted |

---

## 7. Documentation Directory

- **[API Reference](file:///c:/Users/HP/Desktop/CSI%20origins/backend/API_DOCUMENTATION.md)**: Full REST API schema and endpoint contracts.
- **[Privacy & Compliance](file:///c:/Users/HP/Desktop/CSI%20origins/PRIVACY_AND_COMPLIANCE.md)**: Cryptographic specifications and Section 12 PMLA alignment.
- **[Deployment Guide](file:///c:/Users/HP/Desktop/CSI%20origins/DEPLOYMENT_GUIDE.md)**: Cloud architecture, horizontal scaling, and security hardening.
- **[Pitch Deck](file:///c:/Users/HP/Desktop/CSI%20origins/PITCH_DECK.md)**: 8-slide executive presentation.

---

## 8. License

This project is licensed under the Apache 2.0 License.
