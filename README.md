# FraudGuard: Real-Time Transaction Risk Engine & ML Pipeline

An end-to-end, production-grade **Data Engineering & Machine Learning (DE + MLOps)** platform demonstrating real-time transaction stream ingestion, low-latency stateful feature engineering, dual-layer ML inference, and Lakehouse Medallion storage with an enterprise Senior UI/UX audit dashboard.

---

## 🌟 Key Architecture & Highlights

```
[Transaction Stream Ingestion] ➔ [Online Feature Store] ➔ [Dual ML & Rule Guardrails] ➔ [Medallion Lakehouse]
    (Kafka / Event Simulator)        (Rolling Windows / Redis)    (Random Forest + Isolation)     (Bronze/Silver/Gold)
```

1. **Sub-10ms End-to-End SLA**:
   - Computes rolling velocity, statistical Z-scores, and geospatial travel velocity on the fly.
   - Evaluates multi-layer ML fraud probability and returns decisions (`APPROVED`, `REVIEW`, `BLOCKED`) in real time.

2. **The 5 Core Fraud Guardrails & Conditions**:
   - ✈️ **Geographic Travel Velocity**: Calculates physical travel speed between consecutive transactions (`Threshold: Speed ≤ 800 km/h`).
   - ⚡ **5-Minute Burst Pacing**: Detects rapid repeated card swipes from automated scripts (`Threshold: Count ≤ 2 in 5m`).
   - 📈 **Spending Baseline Ratio**: Compares transaction amount to cardholder's 30-day mean (`Threshold: Amount < 8.0x mean`).
   - 🛡️ **Device & Merchant Exposure**: Evaluates unknown hardware against high-risk categories (`Threshold: Trusted device OR low-risk category`).
   - 🤖 **ML Behavioral Anomaly Score**: Unsupervised Isolation Forest outlier detector (`Threshold: Outlier score < 70%`).

3. **Medallion Lakehouse Architecture**:
   - **Bronze**: Raw event ingestion stream (unmodified JSON audit log).
   - **Silver**: Cleansed, schema-enforced, and feature-enriched transaction records.
   - **Gold**: Executive KPI aggregations (loss prevented, fraud rate %, category risk exposure).

4. **Senior-Level Master-Detail UI/UX**:
   - **Live Transactions Feed**: Real-time tabular stream with clear pass/fail guardrail chips.
   - **Condition Audit Panel**: Transparent cardholder profile with side-by-side threshold vs. actual comparisons and plain-English explanations.
   - **Interactive Sandbox & Presets**: 1-click test scenarios (`Normal Coffee`, `Impossible Flight`, `Luxury Spree`, `Crypto Drain`).

---

## 🚀 Quickstart & Running Locally

### 1. Requirements
- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Start the Application
Run using Python or Uvicorn:

```bash
python app.py
```

Or:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Open in Browser
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 📂 Project Structure

```text
├── app.py                     # FastAPI WebSocket & REST Application
├── requirements.txt           # Project dependencies (FastAPI, Uvicorn, Scikit-Learn, WebSockets)
├── .gitignore                 # Standard Python & OS ignore rules
├── engine/
│   ├── generator.py           # Realistic transaction simulator & attack vectors
│   ├── feature_store.py       # Online feature store with sliding time windows & Haversine math
│   ├── ml_model.py            # Random Forest + Isolation Forest + 5 Guardrail conditions
│   ├── medallion_store.py     # Bronze, Silver, and Gold lakehouse simulation
│   └── pipeline.py            # End-to-end streaming orchestrator & latency tracker
├── static/
│   ├── css/style.css          # Minimalist, clean enterprise UI stylesheet
│   ├── js/app.js              # WebSocket client, master-detail audit inspector & sandbox
│   └── favicon.svg            # Custom SVG icon
└── templates/
    └── index.html             # Senior UI/UX dashboard interface
```

---

## 🛡️ Evaluated Guardrails Reference

| Guardrail | Evaluation Rule | Normal State | Violation Trigger |
| :--- | :--- | :--- | :--- |
| **Travel Velocity** | Speed ≤ 800 km/h | Local city travel | Cross-continent transaction within minutes |
| **Burst Frequency** | Count ≤ 2 in 5m | Natural human pacing | Bot / automated script draining card |
| **Spending Ratio** | Amount < 8.0x mean | Typical daily spend | Sudden 30x–50x luxury charge |
| **Device Trust** | Known hardware | Registered smartphone | Untrusted device on crypto/luxury exchange |
| **ML Outlier** | Score < 70% | High-density cluster | Rare multi-dimensional feature combination |
