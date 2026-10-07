import math
import time
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Set

from .generator import USER_PROFILES, HIGH_RISK_CATEGORIES


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth."""
    r = 6371.0  # Earth radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class FeatureStore:
    """
    Low-latency Online Feature Store simulating Redis/Feast.
    Maintains entity sliding windows, user baselines, and computes
    real-time streaming features in sub-millisecond time.
    """

    def __init__(self):
        # User state store: user_id -> profile state
        self.user_baselines: Dict[str, Dict[str, Any]] = {}
        # Sliding event windows: user_id -> deque of (timestamp, amount, location, device_id)
        self.sliding_windows: Dict[str, deque] = {}
        # Known trusted devices per user: user_id -> Set[device_id]
        self.trusted_devices: Dict[str, Set[str]] = {}

        self._initialize_user_baselines()

    def _initialize_user_baselines(self):
        """Seed baselines from user profiles."""
        for u in USER_PROFILES:
            user_id = u["user_id"]
            self.user_baselines[user_id] = {
                "mean_amount": u["mean_amount"],
                "std_amount": u["std_amount"],
                "home_location": u["home_location"],
                "total_historical_txns": 120,
            }
            self.sliding_windows[user_id] = deque(maxlen=200)
            self.trusted_devices[user_id] = {u["device_id"]}

    def compute_features(self, raw_tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates streaming features on incoming event in < 1ms.
        Returns extracted feature vector alongside raw transaction data.
        """
        start_time = time.perf_counter()

        user_id = raw_tx["user_id"]
        amount = float(raw_tx["amount"])
        current_ts = float(raw_tx.get("epoch_time", time.time()))
        current_loc = raw_tx["location"]
        device_id = raw_tx.get("device_id", "")
        category = raw_tx.get("merchant_category", "grocery")

        # Baseline stats
        baseline = self.user_baselines.get(user_id, {
            "mean_amount": 50.0,
            "std_amount": 25.0,
            "home_location": {"city": "Unknown", "lat": 0.0, "lon": 0.0},
        })

        mean_amt = baseline["mean_amount"]
        std_amt = max(baseline["std_amount"], 5.0)

        # 1. Amount Statistical Features
        amount_ratio_to_mean = round(amount / mean_amt, 3)
        amount_z_score = round((amount - mean_amt) / std_amt, 3)

        # 2. Window-based Aggregations (5 min, 1 hr, 24 hr)
        window = self.sliding_windows.get(user_id, deque())
        now_epoch = current_ts

        tx_count_5m = 0
        tx_count_1h = 0
        tx_sum_amount_1h = 0.0
        tx_sum_amount_24h = 0.0

        last_tx_time = None
        last_tx_loc = None

        for item in reversed(window):
            item_ts, item_amt, item_loc, _ = item
            diff_sec = now_epoch - item_ts

            if last_tx_time is None:
                last_tx_time = item_ts
                last_tx_loc = item_loc

            if diff_sec <= 300:  # 5 minutes
                tx_count_5m += 1
            if diff_sec <= 3600:  # 1 hour
                tx_count_1h += 1
                tx_sum_amount_1h += item_amt
            if diff_sec <= 86400:  # 24 hours
                tx_sum_amount_24h += item_amt

        # 3. Geolocation & Velocity Analysis
        home_loc = baseline["home_location"]
        km_from_home = haversine_distance_km(
            home_loc["lat"], home_loc["lon"],
            current_loc["lat"], current_loc["lon"]
        )

        speed_kmh = 0.0
        time_since_last_sec = 0.0
        if last_tx_time and last_tx_loc:
            time_since_last_sec = max(now_epoch - last_tx_time, 1.0)
            dist_from_last = haversine_distance_km(
                last_tx_loc["lat"], last_tx_loc["lon"],
                current_loc["lat"], current_loc["lon"]
            )
            hours_elapsed = time_since_last_sec / 3600.0
            if hours_elapsed > 0:
                speed_kmh = round(dist_from_last / hours_elapsed, 1)

        # 4. Device & Category Profiling
        known_devices = self.trusted_devices.get(user_id, set())
        is_new_device = 1 if device_id not in known_devices else 0
        is_high_risk_cat = 1 if category in HIGH_RISK_CATEGORIES else 0

        # 5. Temporal Features
        dt = datetime.fromtimestamp(current_ts)
        hour_of_day = dt.hour
        is_night_time = 1 if (1 <= hour_of_day <= 5) else 0

        lookup_latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        features = {
            # Identification
            "user_id": user_id,
            "amount": amount,
            # Features fed into ML model
            "amount_ratio_to_mean": amount_ratio_to_mean,
            "amount_z_score": amount_z_score,
            "tx_count_5m": tx_count_5m,
            "tx_count_1h": tx_count_1h,
            "tx_sum_amount_1h": round(tx_sum_amount_1h, 2),
            "tx_sum_amount_24h": round(tx_sum_amount_24h, 2),
            "km_from_home": km_from_home,
            "speed_kmh": speed_kmh,
            "time_since_last_sec": round(time_since_last_sec, 1),
            "is_new_device": is_new_device,
            "is_high_risk_category": is_high_risk_cat,
            "hour_of_day": hour_of_day,
            "is_night_time": is_night_time,
            # Telemetry
            "feature_store_latency_ms": lookup_latency_ms,
        }

        return features

    def commit_transaction(self, raw_tx: Dict[str, Any]):
        """
        Updates state in online store after transaction is processed.
        """
        user_id = raw_tx["user_id"]
        current_ts = float(raw_tx.get("epoch_time", time.time()))
        amount = float(raw_tx["amount"])
        loc = raw_tx["location"]
        device_id = raw_tx.get("device_id", "")

        if user_id not in self.sliding_windows:
            self.sliding_windows[user_id] = deque(maxlen=200)
            self.trusted_devices[user_id] = set()

        self.sliding_windows[user_id].append((current_ts, amount, loc, device_id))

        # Learn device if transaction was verified normal
        if not raw_tx.get("is_fraud_decision", False):
            self.trusted_devices[user_id].add(device_id)

    def get_user_state(self, user_id: str) -> Dict[str, Any]:
        """Inspection endpoint for a user's current feature store state."""
        baseline = self.user_baselines.get(user_id, {})
        window = list(self.sliding_windows.get(user_id, []))
        devices = list(self.trusted_devices.get(user_id, []))

        return {
            "user_id": user_id,
            "baseline": baseline,
            "trusted_devices_count": len(devices),
            "trusted_devices": devices,
            "recent_events_in_memory": len(window),
            "recent_5_events": [
                {"ts": w[0], "amount": w[1], "city": w[2].get("city", "Unknown")}
                for w in window[-5:]
            ],
        }
