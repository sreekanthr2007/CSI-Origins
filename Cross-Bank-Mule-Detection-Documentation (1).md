# Cross-Bank Mule Account Detection Network
### Privacy-Preserving Federated Graph Intelligence for Multi-Bank Fraud Rings

---

## 1. Problem

### 1.1 Who feels this pain, and how often

Every bank in India already runs its own fraud detection system — RBI mandates real-time transaction monitoring, and most banks use AI/ML tools to flag suspicious accounts within their own data. These systems work well *within* a single bank's walls.

The problem appears the moment a mule ring is deliberately spread **across** banks. A typical laundering chain looks like:

```
Victim → Account A (Bank A) → Account B (Bank B) → Account C (Bank C) → ... → Cash-out
```

Each individual hop, viewed by its own bank in isolation, often looks only mildly suspicious — not suspicious enough to cross that bank's internal alert threshold. Bank A sees one outgoing transfer. Bank B sees one incoming, one outgoing. Bank C sees the same. No single bank ever sees the *whole chain*, so no single bank's fraud engine ever produces a high-confidence flag. This is the blind spot that organized mule networks are specifically designed to exploit — spreading a laundering chain across 15-30 institutions makes it invisible to any one of them, even though every one of them individually runs a good fraud system.

This isn't a hypothetical gap. RBI has explicitly advised banks to use network analytics for mule detection, and a new national body — the Indian Digital Payment Intelligence Corporation (IDPIC), incorporated October 2025 — exists specifically to detect and analyze fraud across India's digital payments ecosystem in real time, precisely because no single institution can see the cross-bank picture alone.

### 1.2 Today's workaround

Currently, cross-institution mule detection happens **after the fact**, and manually:
- A victim files a complaint or a bank files a Suspicious Transaction Report (STR) to FIU-IND
- Investigators manually request transaction records from each subsequent bank in the chain, one at a time, through formal legal/regulatory channels
- This process takes days to weeks — by which point the money has long since been withdrawn as cash

### 1.3 Why it falls short

- **Speed mismatch**: mule chains move money in minutes to hours; manual inter-bank investigation takes days
- **Visibility mismatch**: each bank's automated system only ever sees its own slice, so the "weak but individually below-threshold" signals across 3-4 banks never get combined into the strong signal they represent together
- **No standing infrastructure**: there is currently no automated, privacy-compliant channel for banks to proactively correlate their weak signals with each other before an investigator manually intervenes

### 1.4 Evidence

- RBI has directed banks to deploy AI/ML-based real-time monitoring and specifically use **network analytics to identify mule networks**
- The formation of IDPIC (Oct 2025) as a dedicated cross-institution fraud intelligence body confirms this gap is recognized at the regulatory level, not just anecdotally
- Documented mule account behavioral patterns (high-volume credits from many senders, near-immediate full withdrawal, dormant accounts suddenly active) are consistent, well-known signatures — the detection logic is understood; what's missing is the cross-bank correlation layer to apply it at

---

## 2. Idea

Build a **privacy-preserving cross-bank correlation layer** that sits *above* existing bank fraud systems — not replacing them, but connecting their outputs.

Each bank already produces a local risk signal for its own accounts. Our system's job is to determine when several **individually weak signals**, spread across different banks, form a **structurally strong pattern** — a fast-moving chain, a collector/distributor node, a ring — that no single bank could see on its own.

Critically, the system is designed so that:
- No raw account numbers, names, PAN, phone numbers, or transaction narrations ever leave a bank
- The central system can detect *that* a ring exists and *which banks* are involved, without ever being able to independently identify *who* the people are
- Only the specific bank that owns a flagged account can de-anonymize it, using its own internal records

---

## 3. Solution — Detailed Design

### 3.1 System Overview — Two Operating Flows

**Flow A — Continuous Background Monitoring (always-on)**
Every bank continuously contributes anonymized, hashed **boundary-crossing edges** (inter-bank transfers only — never intra-bank data) to a central graph. This graph is used to compute velocity, fan-in/fan-out, and pass-through patterns across the whole system, in real time.

**Flow B — Triggered Deep Investigation (on-demand)**
Once Flow A flags a suspicious account, the central system requests a **scoped, targeted neighborhood pull** from the specific bank(s) touching that account — including their intra-bank edges around that one account — to reconstruct the fuller local picture (who it received from, who it sent to), bounded by strict stopping criteria (see §3.6).

### 3.1.1 Flow A (Edge Sharing) vs. Federated Learning (§3.9) — Which One Are We Actually Building?

These are two distinct architectures for solving the same underlying problem, and the project deliberately builds one and defers the other. This distinction matters because a judge who knows federated learning will otherwise ask: *"If you're using federated learning, why do you need a central graph at all?"*

**What we are building for the hackathon (MVP): Flow A, hashed edge-sharing.**
Banks contribute hashed inter-bank edges to a central graph, which we construct and analyze directly. We chose this as the MVP specifically because it is **explainable and traceable** — every flag our system raises can be traced back to a specific edge, a specific chain, a specific pass-through ratio. This matters for a fraud/compliance use case: an investigator (or a judge) can ask "why was this flagged?" and get a concrete subgraph as the answer, not a black-box score. A GNN trained via federated learning cannot offer this same level of per-decision traceability without significant additional explainability tooling.

**What we are deferring to the roadmap (v2): Federated Learning (§3.9).**
Edge-sharing assumes banks are willing to contribute anonymized, hashed edge data to a shared graph at all. In a real deployment, some banks (or regulators) may object even to *hashed* edges leaving the institution, no matter how the identity protection is structured. Federated learning is the fallback for exactly that scenario — it lets banks contribute to a shared fraud-detection model by sharing only trained model weights/gradients, with zero transaction-level data, hashed or otherwise, ever leaving the bank. We position this as the v2 answer to "what if a bank won't even share hashed edges" — not as a parallel system running alongside Flow A.

**One-line summary for the deck:** *"We build the edge-sharing graph (Flow A) for the hackathon because it's explainable and demoable end-to-end. Federated learning (§3.9) is our stated v2 path for banks unwilling to share even anonymized edges — the two are sequential fallback tiers, not two systems running at once."*

### 3.2 What Data Actually Moves Between Banks

Each bank contributes **rows of edge data**, not raw transaction dumps and not their internal graphs:

```
hashed_sender_id, hashed_receiver_id, amount, timestamp, cross_bank_flag, local_risk_score
```

- No names, PAN, Aadhaar, phone numbers, or transaction narrations are ever included
- For Flow A, only **inter-bank** edges are shared (a transaction that crosses a bank boundary) — intra-bank activity stays inside the bank
- The central system constructs the actual graph itself, from these edges; it never receives a bank's own pre-built graph (which could leak structural/identity information)

### 3.3 The Hashing Scheme (Identity Protection)

This is the core privacy mechanism, and it uses **two distinct hash types for two distinct purposes** — conflating them was an early design flaw we identified and corrected.

**(a) Standing / Rotated Hash — used for Flow A (continuous monitoring)**

```
node_id = HMAC-SHA256( key = registry_shared_key_current_period, message = account_number + IFSC_code )
```

- The key is held by a trusted central registry role (conceptually similar to how NPCI already acts as a trusted, neutral rail across all Indian banks for UPI routing)
- Because the **formula and key are shared** (not bank-specific), any bank that legitimately knows an account's number + IFSC (which is required for any transfer to route in the first place) computes the *same* hash that the account's own bank would compute — this is what allows the graph to connect `A → B → C` correctly across institutions without ever exchanging raw account numbers
- The key is **rotated periodically** (e.g. monthly) — this bounds the exposure window if the key is ever compromised, without breaking the ability to track behavior within that window
- Even with a rotated key, this hash is intentionally NOT persisted in raw form anywhere it can be batch-reversed — see §3.3(c)

**(b) Ephemeral / Investigation-Specific Hash — used for Flow B (targeted deep-dive)**

```
investigation_node_id = HMAC-SHA256( key = one_time_investigation_salt, message = account_number + Bank_ID )
```

- Generated fresh per investigation, and **destroyed once the case closes**
- Used only for the deep local-neighborhood pull once an account is already flagged — this data doesn't need to persist beyond the investigation
- Ensures that even if an investigation's output is later leaked, the ephemeral hash cannot be used to re-identify or re-track the same account in any future or unrelated context

**(c) No-Persistence Hashing Service (hardening layer)**

Rather than distributing the registry key broadly, all hashing happens through a single, tightly access-controlled hashing microservice:
- Banks send account number + IFSC over encrypted transport (TLS) only at the moment of computing a hash
- The service computes the HMAC and returns it — **it never logs or stores the raw input**
- The registry key itself lives only inside this service (ideally a secure enclave), never distributed to application code elsewhere
- Result: even a full breach of the central graph database yields only hash values with no stored raw inputs anywhere to correlate against

**(d) Why not just encrypt instead of hash?**
Encryption is reversible by design (whoever holds the decryption key can always recover the original value) — which is exactly the property we don't want centrally. One-way hashing with a securely held, rotated, non-persisted key ensures that even the system operators cannot reverse the data; only the originating bank (which holds its own internal lookup table of `account → hash`, built locally) can map a hash back to a real account.

### 3.4 Graph Construction

The central system ingests the flat edge records from all participating banks and builds the actual graph itself:
- Each unique hashed account ID becomes a **node**
- Each transaction record becomes a **directed edge**, carrying amount, timestamp, and the contributing bank's local risk score as attributes
- Implementation: NetworkX for prototype scale; a graph database (e.g. Neo4j) for a more production-representative build

### 3.5 Mule-Pattern Detection — Structural + Behavioral Signals

Individual account scoring alone is unreliable — the same signal combination is far more predictive at the **component (subgraph) level**. Signals used:

**Structural (graph-based):**
- **Short cycle / chain length** — mule chains are typically 2-7 hops, unlike the dense, longer-range connectivity of normal transaction graphs
- **Fan-in / fan-out asymmetry** — a "collector" node (many senders, one account) or "distributor" node (one account, many receivers) within a short time window
- **Pass-through ratio** — `amount_sent_within_N_hours / amount_received`; a ratio near 1 means the account is acting as a pipe, not a store of value
- **First-time edge** — a large-value transfer between two accounts with no prior transaction history is a stronger anomaly than the same transfer between accounts with an established relationship
- **Component-level anomaly scoring** — flag the whole connected subgraph together when it shows dense internal fast-pass-through activity, rather than scoring single nodes in isolation

**Behavioral (contributed by each bank's own local_risk_score):**
- Account age vs. transaction volume mismatch (freshly opened or dormant-then-reactivated accounts)
- Round-figure transaction amounts
- Amounts structured just under regulatory reporting thresholds
- KYC-declared income/occupation mismatch with observed transaction volume

**Combining signals:**
An XGBoost/Random Forest classifier is trained on these structural + behavioral features (using labeled synthetic mule rings for the prototype), producing a single `mule_probability` score per flagged component, with SHAP-based explainability showing which features drove the flag (e.g., "87% pass-through ratio, 3-hop chain, 40-minute window").

**Synthetic data generation strategy:**
We generate the base transaction graph using an **Erdős–Rényi random graph** to model normal, everyday transaction traffic (legitimate accounts, random low-density connectivity, realistic amount/timing distributions). Into this base graph, we then **inject labeled mule motifs** — short directed chains (2-7 hops) and star-shaped collector/distributor patterns — at a **~10% contamination rate**. Each injected motif is tagged with ground-truth labels (which nodes/edges are part of a synthetic ring), which gives us a statistically grounded way to train and validate the XGBoost classifier and measure precision/recall, without needing real bank data. This also lets us demo the bounded pattern-decay traversal (§3.6) against a chain of known, controllable length.

### 3.6 Bounded Graph Traversal — Solving the "How Far Do We Look" Problem

Unbounded traversal across a laundering chain spanning many banks is computationally and operationally unworkable. The system uses a two-part stopping rule:

**1. Pattern-decay stopping (primary rule):**
Expand the investigation outward (both backward toward the money's origin and forward toward cash-out) hop by hop, but at each hop, re-check the same mule-pattern features (pass-through ratio, timing gap, first-time-edge, local risk score). The moment an edge fails this test — e.g., the money sat for weeks, or the accounts have a long prior relationship — traversal stops in that direction. This avoids treating legitimate upstream/downstream activity as part of the ring.

**2. Hard caps (backstop, guards against evasion and runaway cost):**
- Maximum hop depth per direction (e.g. 5-7 hops)
- Maximum number of institutions touched per single investigation (e.g. 10-15)
- A fixed budget of targeted "neighborhood pull" requests per investigation

Beyond these caps, the partial graph is handed to human investigators, explicitly labeled as depth-limited — mirroring how real AML investigations already escalate from automated triage to manual/legal process once a case grows large enough.

### 3.7 Why the Central System Can't See Withdrawals — and Why That's OK

Cash withdrawal is the end of any digital trail — there is no "receiving account" for cash, so no edge is ever generated for it, and this is an honest, unavoidable limitation, not a design gap. The system works around this by shifting the detection window earlier: the **terminal bank in a chain** (the one from which cash-out occurs) can locally compute a simple flag — `received_via_interbank_transfer = true AND withdrawn_as_cash_within_N_hours = true` — entirely from its own internal data, with no privacy issue, and contribute that as part of its local_risk_score. The system's real value is catching the ring **while the money is still moving digitally**, so the terminal bank can act (freeze, hold, escalate) before cash-out completes — not after.

### 3.8 De-Anonymization and Action — Who Can Actually Trace an Account

The central system never holds the secret keys/salts needed to reverse any hash back to a real account. When a component is flagged:
1. The central system identifies **which bank(s)** submitted the flagged hashes (known from the submission channel, not from decoding the hash itself)
2. It sends a targeted alert to that specific bank: flagged hash(es), risk score, and the pattern detected
3. **Only that bank**, using its own internally held mapping (built with its own key), looks up the real account
4. That bank takes action through its own existing compliance process (freeze, manual review, STR filing to FIU-IND)

The system is explicitly an **intelligence and correlation layer, not an enforcement or surveillance layer** — de-anonymization and action always happen at the bank level.

### 3.9 Federated Local Scoring (Flow A's Learning Layer)

In parallel with the edge-sharing described above, each bank can also train a lightweight local model (or GNN) on its own account graph to compute suspicion scores, and share only the resulting **model weight updates** (not raw data, not the graph) with a central aggregator using standard federated averaging. This lets the global model improve from patterns observed across all banks without any bank's underlying data ever leaving its walls — the same mechanism already used in large-scale federated learning deployments (e.g. predictive text on mobile keyboards).

---

## 4. How Privacy Is Maintained — Summary of Guarantees

| Layer | What it protects against | Mechanism |
|---|---|---|
| No raw PII ever shared | Identity exposure | Only hashed IDs + non-identifying metadata (amount, timestamp, flags) cross bank boundaries |
| Intra-bank data stays local (Flow A) | Full internal graph exposure | Only inter-bank boundary-crossing edges are contributed to continuous monitoring |
| One-way hashing (not encryption) | Central system reversing identities | HMAC-based hashing; no decryption key exists anywhere centrally |
| Rotated standing key | Long-term correlation if key leaks | Key rotated periodically (e.g. monthly); old hashes stop matching new ones |
| Ephemeral investigation salt | Long-term tracking from a single leaked investigation | Salt generated fresh per case, destroyed on case closure |
| No-persistence hashing service | Bulk reversal via data breach | Raw account number + IFSC never stored — only ever used transiently to compute a hash |
| Scoped, triggered deep-dives (Flow B) | Bulk/unjustified data collection | Intra-bank neighborhood data is only requested for accounts already flagged, bounded by hop/institution caps |
| Bank-only de-anonymization | Central system or attacker identifying individuals | Only the originating bank, using its own internally held mapping, can resolve a hash back to a real account |
| Federated local scoring | Raw data or model exposure across banks | Only trained model weight updates are shared, never transaction data |

### 4.1 Known Residual Risk (stated honestly)

If the central registry key were compromised, an attacker could in principle brute-force plausible `account_number + IFSC` combinations and compute matching canonical hashes, then attempt to resolve some of those to names via existing UPI account-verification lookup features. This would **not** expose transaction history, PAN, Aadhaar, phone numbers, or enable fund transfer/theft — account number + IFSC alone cannot move money out of an account. This residual risk is mitigated by key rotation, restricting key custody to a single access-controlled hashing service, and (as a stated production roadmap item) migrating the matching step to **Private Set Intersection (PSI)** — a cryptographic protocol that lets two parties discover shared elements between their datasets without a persistent shared secret ever existing, eliminating this class of risk entirely. PSI is a well-established technique (used, for example, in secure contact-discovery systems), deliberately scoped out of the hackathon build due to implementation complexity, but included here as the correct next step.

---

## 5. Honest Scope Boundaries

**In scope (built/prototyped):** synthetic multi-bank simulation, standing + ephemeral hashing scheme, graph construction from hashed edges, structural + behavioral mule-pattern scoring, bounded pattern-decay traversal, targeted investigation flow, explainability layer.

**Out of scope (stated roadmap, not built):** real bank integration, live PSI protocol implementation, production-grade secure enclave for key custody, real-time GNN training infrastructure at bank scale, legal/regulatory onboarding of participating institutions.

**Positioning:** this is a correlation and alerting layer that sits on top of banks' existing, already-mandated fraud detection systems — not a replacement for them, and not a system capable of independently identifying or acting against any individual.
