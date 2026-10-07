import time
from typing import Dict, Any, Optional

from .feature_store import FeatureStore
from .ml_model import FraudMLPipeline
from .medallion_store import MedallionStore


class FraudDetectionPipeline:
    """
    End-to-End Orchestrator:
    Ingestion -> Bronze -> Feature Store Lookup -> ML Inference -> Silver -> Gold
    """

    def __init__(self):
        self.feature_store = FeatureStore()
        self.ml_pipeline = FraudMLPipeline()
        self.medallion_store = MedallionStore()

    def process_transaction(self, raw_tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single transaction through the complete data & ML pipeline.
        Tracks precise step latencies to demonstrate sub-second SLA performance.
        """
        total_start = time.perf_counter()

        # Step 1: Ingest to Bronze Lakehouse Layer
        self.medallion_store.ingest_bronze(raw_tx)

        # Step 2: Feature Store Lookup & Dynamic Calculation
        features = self.feature_store.compute_features(raw_tx)

        # Step 3: ML Inference (Supervised + Unsupervised Anomaly Scoring + Rules)
        ml_result = self.ml_pipeline.predict(features)

        # Step 4: Commit state to Feature Store
        is_blocked = (ml_result["decision"] == "BLOCKED")
        raw_tx_copy = dict(raw_tx)
        raw_tx_copy["is_fraud_decision"] = is_blocked
        self.feature_store.commit_transaction(raw_tx_copy)

        # Step 5: Construct Unified Enriched Record
        total_latency_ms = round((time.perf_counter() - total_start) * 1000.0, 2)

        enriched_record = {
            # Transaction Metadata
            "transaction_id": raw_tx["transaction_id"],
            "timestamp": raw_tx["timestamp"],
            "user_id": raw_tx["user_id"],
            "user_name": raw_tx["user_name"],
            "card_number": raw_tx["card_number"],
            "card_type": raw_tx["card_type"],
            "amount": raw_tx["amount"],
            "currency": raw_tx["currency"],
            "merchant": raw_tx["merchant"],
            "merchant_category": raw_tx["merchant_category"],
            "location": raw_tx["location"],
            "device_id": raw_tx["device_id"],
            "simulated_ground_truth": raw_tx.get("is_simulated_ground_truth", False),
            "simulated_fraud_type": raw_tx.get("simulated_fraud_type"),

            # Extracted Feature Insights
            "features": features,

            # ML Scoring & Decision
            "decision": ml_result["decision"],
            "risk_score": ml_result["risk_score"],
            "rf_fraud_probability": ml_result["rf_fraud_probability"],
            "anomaly_score": ml_result["anomaly_score"],
            "risk_factors": ml_result["risk_factors"],
            "conditions": ml_result.get("conditions", []),

            # Pipeline Telemetry
            "telemetry": {
                "feature_store_ms": features["feature_store_latency_ms"],
                "ml_inference_ms": ml_result["inference_latency_ms"],
                "total_pipeline_ms": total_latency_ms,
            },
            "total_latency_ms": total_latency_ms,
        }

        # Step 6: Write to Silver & Update Gold Lakehouse Aggregates
        self.medallion_store.write_silver(enriched_record)
        self.medallion_store.update_gold(enriched_record)

        return enriched_record
