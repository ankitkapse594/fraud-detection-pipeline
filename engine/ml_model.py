import time
import numpy as np
from typing import Dict, Any, List, Tuple
from sklearn.ensemble import RandomForestClassifier, IsolationForest


FEATURE_COLUMNS = [
    "amount",
    "amount_ratio_to_mean",
    "amount_z_score",
    "tx_count_5m",
    "tx_count_1h",
    "km_from_home",
    "speed_kmh",
    "is_new_device",
    "is_high_risk_category",
    "is_night_time",
]


class FraudMLPipeline:
    """
    Dual-layer ML Inference Engine:
    - Layer 1: Supervised Random Forest Classifier (Trained on imbalanced transactions)
    - Layer 2: Unsupervised Isolation Forest (Zero-day Anomaly Detector)
    - Layer 3: Rule Safety Guard & Human-readable Explainability
    """

    def __init__(self):
        self.rf_classifier = RandomForestClassifier(
            n_estimators=45,
            max_depth=8,
            random_state=42,
            n_jobs=-1,
        )
        self.isolation_forest = IsolationForest(
            n_estimators=35,
            contamination=0.08,
            random_state=42,
            n_jobs=-1,
        )
        self.is_trained = False
        self._bootstrap_models()

    def _bootstrap_models(self):
        """
        Synthesizes a realistic training distribution of 4,000 normal and 300 fraud
        feature vectors to bootstrap models instantly upon initialization.
        """
        np.random.seed(42)
        n_normal = 3500
        n_fraud = 300

        # Normal transactions feature distribution
        norm_amounts = np.random.exponential(scale=45.0, size=n_normal) + 5.0
        norm_ratios = np.random.normal(loc=1.0, scale=0.35, size=n_normal)
        norm_ratios = np.clip(norm_ratios, 0.1, 3.0)
        norm_z = (norm_amounts - 50.0) / 25.0
        norm_cnt_5m = np.random.poisson(lam=0.08, size=n_normal)
        norm_cnt_1h = np.random.poisson(lam=0.4, size=n_normal)
        norm_km = np.random.exponential(scale=12.0, size=n_normal)
        norm_speed = np.random.exponential(scale=15.0, size=n_normal)
        norm_new_dev = np.random.binomial(n=1, p=0.04, size=n_normal)
        norm_high_risk = np.random.binomial(n=1, p=0.06, size=n_normal)
        norm_night = np.random.binomial(n=1, p=0.05, size=n_normal)

        X_normal = np.column_stack([
            norm_amounts, norm_ratios, norm_z, norm_cnt_5m, norm_cnt_1h,
            norm_km, norm_speed, norm_new_dev, norm_high_risk, norm_night
        ])
        y_normal = np.zeros(n_normal)

        # Fraudulent transactions feature distribution
        high_fraud = np.random.uniform(700.0, 4500.0, size=n_fraud // 2)
        micro_fraud = np.random.uniform(0.99, 2.99, size=n_fraud - (n_fraud // 2))
        fraud_amounts = np.concatenate([high_fraud, micro_fraud])
        np.random.shuffle(fraud_amounts)
        fraud_ratios = np.random.uniform(5.0, 45.0, size=n_fraud)
        fraud_z = np.random.uniform(4.0, 25.0, size=n_fraud)
        fraud_cnt_5m = np.random.poisson(lam=3.5, size=n_fraud)
        fraud_cnt_1h = np.random.poisson(lam=6.0, size=n_fraud)
        fraud_km = np.random.uniform(800.0, 9500.0, size=n_fraud)
        fraud_speed = np.random.uniform(600.0, 25000.0, size=n_fraud)
        fraud_new_dev = np.random.binomial(n=1, p=0.75, size=n_fraud)
        fraud_high_risk = np.random.binomial(n=1, p=0.80, size=n_fraud)
        fraud_night = np.random.binomial(n=1, p=0.35, size=n_fraud)

        X_fraud = np.column_stack([
            fraud_amounts, fraud_ratios, fraud_z, fraud_cnt_5m, fraud_cnt_1h,
            fraud_km, fraud_speed, fraud_new_dev, fraud_high_risk, fraud_night
        ])
        y_fraud = np.ones(n_fraud)

        X = np.vstack([X_normal, X_fraud])
        y = np.concatenate([y_normal, y_fraud])

        # Train models
        self.rf_classifier.fit(X, y)
        self.isolation_forest.fit(X)
        self.is_trained = True

    def _extract_feature_vector(self, features: Dict[str, Any]) -> np.ndarray:
        return np.array([[features[col] for col in FEATURE_COLUMNS]], dtype=float)

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes sub-10ms dual-model ML scoring with explainability reasons.
        """
        start_time = time.perf_counter()
        X_vec = self._extract_feature_vector(features)

        # 1. Supervised Fraud Probability (0.0 to 1.0)
        rf_prob = float(self.rf_classifier.predict_proba(X_vec)[0][1])

        # 2. Unsupervised Anomaly Score (normalized 0.0 to 1.0, higher = more anomalous)
        raw_if_score = float(self.isolation_forest.decision_function(X_vec)[0])
        # Map raw decision function [-0.5, 0.5] roughly to [1.0, 0.0]
        anomaly_score = float(np.clip(0.5 - (raw_if_score * 1.5), 0.0, 1.0))

        # 3. Rule Safety Guard & Heuristic Boosts
        rules_triggered = []
        rule_score_boost = 0.0

        if features["speed_kmh"] > 800.0:
            rules_triggered.append(
                f"Impossible Travel: {features['speed_kmh']:,.0f} km/h between locations"
            )
            rule_score_boost += 0.45

        if features["tx_count_5m"] >= 3:
            rules_triggered.append(
                f"Velocity Spike: {features['tx_count_5m'] + 1} transactions in 5 minutes"
            )
            rule_score_boost += 0.35

        if features["amount_ratio_to_mean"] >= 8.0:
            rules_triggered.append(
                f"Severe Spending Spike: {features['amount_ratio_to_mean']:.1f}x higher than user's normal average"
            )
            rule_score_boost += 0.30

        if features["is_new_device"] and features["is_high_risk_category"]:
            rules_triggered.append("Untrusted New Device used in High-Risk Merchant Category")
            rule_score_boost += 0.25

        if features["km_from_home"] > 2500.0 and features["is_new_device"]:
            rules_triggered.append(
                f"Cross-Continent Anomaly: {features['km_from_home']:,.0f} km from registered home location"
            )
            rule_score_boost += 0.20

        # Combined composite risk score (0 to 100)
        base_combined = (0.60 * rf_prob) + (0.40 * anomaly_score)
        combined_prob = min(1.0, base_combined + rule_score_boost)
        risk_score = round(combined_prob * 100.0, 1)

        # Explicit Business & ML Conditions Evaluation
        speed_passed = bool(features["speed_kmh"] <= 800.0)
        vel_passed = bool(features["tx_count_5m"] < 3)
        amount_passed = bool(features["amount_ratio_to_mean"] < 8.0)
        device_passed = bool(not (features["is_new_device"] and features["is_high_risk_category"]))
        ml_passed = bool(anomaly_score < 0.70)

        conditions = [
            {
                "id": "speed",
                "name": "Geographic Travel Velocity",
                "icon": "✈️",
                "rule": "Speed ≤ 800 km/h",
                "actual": f"{features['speed_kmh']:,.0f} km/h",
                "passed": speed_passed,
                "description": "Travel speed between locations exceeds 800 km/h. Physically impossible flight travel." if not speed_passed else "Travel velocity between transactions is physically normal and plausible."
            },
            {
                "id": "velocity_5m",
                "name": "5-Minute Burst Frequency",
                "icon": "⚡",
                "rule": "Count ≤ 2 in 5m",
                "actual": f"{features['tx_count_5m']} in last 5m",
                "passed": vel_passed,
                "description": "Card burst detected: multiple rapid transactions in under 5 minutes (bot/script signature)." if not vel_passed else "Transaction pacing is consistent with natural human browsing."
            },
            {
                "id": "amount_ratio",
                "name": "Spending Baseline Ratio",
                "icon": "📈",
                "rule": "Amount < 8.0x average",
                "actual": f"{features['amount_ratio_to_mean']:.1f}x (${features['amount']:.2f})",
                "passed": amount_passed,
                "description": f"Severe spending spike: {features['amount_ratio_to_mean']:.1f}x higher than this customer's 30-day baseline." if not amount_passed else "Amount is within reasonable range of customer's historical average spend."
            },
            {
                "id": "device_category",
                "name": "Device & Merchant Trust",
                "icon": "🛡️",
                "rule": "Trusted hardware OR standard merchant",
                "actual": "Untrusted Device + High Risk" if not device_passed else "Verified / Standard",
                "passed": device_passed,
                "description": "Unrecognized hardware fingerprint transacting in high-risk crypto/luxury category." if not device_passed else "Transaction performed on a known device or at a standard retail merchant."
            },
            {
                "id": "ml_anomaly",
                "name": "ML Behavioral Anomaly Score",
                "icon": "🤖",
                "rule": "Isolation score < 70%",
                "actual": f"{round(anomaly_score * 100)}% outlier score",
                "passed": ml_passed,
                "description": f"Isolation Forest algorithm detected anomalous feature combination ({round(anomaly_score * 100)}% confidence)." if not ml_passed else "ML multi-dimensional evaluation matches legitimate behavioral baseline."
            }
        ]

        # Tri-state Decisioning Logic
        if risk_score >= 70.0:
            decision = "BLOCKED"
        elif risk_score >= 40.0:
            decision = "REVIEW"
        else:
            decision = "APPROVED"

        # Generate Explainability Top Factors
        risk_factors = list(rules_triggered)
        if rf_prob > 0.65 and not any("ML" in r for r in risk_factors):
            risk_factors.append(f"Supervised ML Fraud Pattern Match ({round(rf_prob * 100)}% confidence)")
        if anomaly_score > 0.70 and not any("Anomaly" in r for r in risk_factors):
            risk_factors.append(f"Unsupervised Behavioral Anomaly ({round(anomaly_score * 100)}% outlier score)")

        if not risk_factors:
            risk_factors.append("Standard behavioral pattern within normal limits")

        inference_latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        return {
            "decision": decision,
            "risk_score": risk_score,
            "rf_fraud_probability": round(rf_prob, 3),
            "anomaly_score": round(anomaly_score, 3),
            "risk_factors": risk_factors,
            "conditions": conditions,
            "inference_latency_ms": inference_latency_ms,
        }
