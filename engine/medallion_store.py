import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List


class MedallionStore:
    """
    Simulates a Lakehouse Medallion Architecture (Bronze -> Silver -> Gold)
    demonstrating enterprise Data Engineering storage patterns.
    """

    def __init__(self, buffer_size: int = 500):
        # Bronze: Raw Ingestion Stream (unmodified JSON events)
        self.bronze_records = deque(maxlen=buffer_size)
        self.bronze_count: int = 0
        self.bronze_bytes: int = 0

        # Silver: Cleansed, Enriched, Feature-Joined Lakehouse Records
        self.silver_records = deque(maxlen=buffer_size)
        self.silver_count: int = 0

        # Gold: Business Analytics & Operational KPI Aggregates
        self.total_volume_usd: float = 0.0
        self.fraud_volume_blocked_usd: float = 0.0
        self.approved_count: int = 0
        self.review_count: int = 0
        self.blocked_count: int = 0

        # Category analytics: category -> {"count": int, "fraud_count": int, "volume": float}
        self.category_metrics: Dict[str, Dict[str, Any]] = {}

        # Latency tracking
        self.latencies_ms = deque(maxlen=100)

        # Risk factor frequency breakdown
        self.risk_factor_counts: Dict[str, int] = {}

    def ingest_bronze(self, raw_event: Dict[str, Any]):
        """Append raw incoming payload directly to Bronze layer."""
        self.bronze_records.append(raw_event)
        self.bronze_count += 1
        # Approximate payload size
        self.bronze_bytes += len(str(raw_event).encode("utf-8"))

    def write_silver(self, enriched_record: Dict[str, Any]):
        """Persist cleansed and enriched feature-engineered record to Silver."""
        self.silver_records.append(enriched_record)
        self.silver_count += 1

    def update_gold(self, processed_txn: Dict[str, Any]):
        """Update live aggregate KPIs in Gold layer."""
        amount = float(processed_txn.get("amount", 0.0))
        decision = processed_txn.get("decision", "APPROVED")
        category = processed_txn.get("merchant_category", "general")
        total_latency = float(processed_txn.get("total_latency_ms", 5.0))
        factors = processed_txn.get("risk_factors", [])

        self.total_volume_usd += amount
        self.latencies_ms.append(total_latency)

        if decision == "BLOCKED":
            self.blocked_count += 1
            self.fraud_volume_blocked_usd += amount
        elif decision == "REVIEW":
            self.review_count += 1
        else:
            self.approved_count += 1

        # Update category metrics
        if category not in self.category_metrics:
            self.category_metrics[category] = {"count": 0, "fraud_count": 0, "volume": 0.0}

        self.category_metrics[category]["count"] += 1
        self.category_metrics[category]["volume"] = round(self.category_metrics[category]["volume"] + amount, 2)
        if decision == "BLOCKED":
            self.category_metrics[category]["fraud_count"] += 1

        # Track risk factors
        for f in factors:
            if "Standard behavioral" not in f:
                short_factor = f.split(":")[0] if ":" in f else f
                self.risk_factor_counts[short_factor] = self.risk_factor_counts.get(short_factor, 0) + 1

    def get_gold_metrics(self) -> Dict[str, Any]:
        """Returns consolidated business metrics for executive dashboards."""
        total_txns = self.approved_count + self.review_count + self.blocked_count
        fraud_rate_pct = round((self.blocked_count / total_txns * 100.0), 2) if total_txns > 0 else 0.0
        avg_latency = round(sum(self.latencies_ms) / len(self.latencies_ms), 2) if self.latencies_ms else 0.0

        return {
            "total_transactions": total_txns,
            "approved_count": self.approved_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "total_volume_usd": round(self.total_volume_usd, 2),
            "fraud_volume_blocked_usd": round(self.fraud_volume_blocked_usd, 2),
            "fraud_rate_pct": fraud_rate_pct,
            "avg_latency_ms": avg_latency,
            "category_metrics": self.category_metrics,
            "top_risk_factors": sorted(
                [{"name": k, "count": v} for k, v in self.risk_factor_counts.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:5],
            "medallion_stats": {
                "bronze_count": self.bronze_count,
                "bronze_kb": round(self.bronze_bytes / 1024.0, 1),
                "silver_count": self.silver_count,
                "gold_kpi_updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }

    def get_recent_silver_records(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetch the most recent processed Silver records."""
        return list(reversed(list(self.silver_records)))[:limit]
