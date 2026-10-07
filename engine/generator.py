import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Realistic locations for simulated users and transactions
CITIES = [
    {"city": "New York", "country": "USA", "lat": 40.7128, "lon": -74.0060},
    {"city": "San Francisco", "country": "USA", "lat": 37.7749, "lon": -122.4194},
    {"city": "Chicago", "country": "USA", "lat": 41.8781, "lon": -87.6298},
    {"city": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
    {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lon": 13.4050},
    {"city": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {"city": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
    {"city": "Lagos", "country": "Nigeria", "lat": 6.5244, "lon": 3.3792},
    {"city": "Sao Paulo", "country": "Brazil", "lat": -23.5505, "lon": -46.6333},
]

MERCHANTS_BY_CATEGORY = {
    "grocery": [
        ("Whole Foods Market", 15.0, 140.0),
        ("Trader Joe's", 10.0, 95.0),
        ("Walmart Supercenter", 20.0, 180.0),
        ("Target", 12.0, 130.0),
    ],
    "dining": [
        ("Starbucks Coffee", 4.5, 18.0),
        ("Chipotle Mexican Grill", 11.0, 32.0),
        ("Sweetgreen", 14.0, 26.0),
        ("The Capital Grille", 85.0, 350.0),
    ],
    "digital_services": [
        ("Netflix Subscription", 15.99, 22.99),
        ("Spotify Premium", 10.99, 16.99),
        ("Amazon Web Services", 45.0, 450.0),
        ("Steam Games Store", 9.99, 79.99),
    ],
    "travel": [
        ("Uber Technologies", 12.0, 65.0),
        ("Delta Air Lines", 180.0, 850.0),
        ("Airbnb Stay", 120.0, 1100.0),
        ("Hilton Hotels", 160.0, 750.0),
    ],
    "electronics": [
        ("Apple Store Retail", 199.0, 2800.0),
        ("Best Buy Electronics", 89.0, 1400.0),
        ("Newegg Computer", 120.0, 1850.0),
    ],
    "luxury_goods": [
        ("Rolex Boutique", 1500.0, 8500.0),
        ("Gucci Flagship", 450.0, 3200.0),
        ("Tiffany & Co.", 350.0, 4200.0),
    ],
    "crypto": [
        ("Binance Global Pay", 250.0, 5000.0),
        ("Coinbase Commerce", 150.0, 4500.0),
        ("Kraken Exchange", 300.0, 6000.0),
    ],
}

HIGH_RISK_CATEGORIES = {"crypto", "luxury_goods", "electronics"}

# User Persona Profiles
USER_PROFILES = [
    {
        "user_id": f"USR-{1000 + i}",
        "name": name,
        "home_location": loc,
        "mean_amount": mean_amt,
        "std_amount": std_amt,
        "card_number": f"{random.randint(4000, 4999)} •••• •••• {random.randint(1000, 9999)}",
        "card_type": random.choice(["Visa Signature", "Mastercard Platinum", "Amex Gold"]),
        "device_id": f"DEV-{uuid.uuid4().hex[:8].upper()}",
    }
    for i, (name, loc, mean_amt, std_amt) in enumerate([
        ("Alex Mercer", CITIES[0], 48.0, 25.0),
        ("Sarah Jenkins", CITIES[1], 72.0, 40.0),
        ("David Zhao", CITIES[2], 55.0, 30.0),
        ("Emma Watson", CITIES[3], 65.0, 35.0),
        ("Lukas Becker", CITIES[4], 50.0, 28.0),
        ("Priya Sharma", CITIES[5], 60.0, 32.0),
        ("Kenji Sato", CITIES[6], 85.0, 45.0),
        ("Liam O'Connor", CITIES[7], 58.0, 30.0),
        ("Elena Rostova", CITIES[0], 90.0, 50.0),
        ("Mateo Silva", CITIES[9], 42.0, 22.0),
    ])
]


class TransactionGenerator:
    """
    Generates continuous stream of realistic fintech transactions
    with configurable normal traffic and injected fraud patterns.
    """

    def __init__(self, fraud_probability: float = 0.08):
        self.users = USER_PROFILES
        self.fraud_probability = fraud_probability
        self.last_user_tx_time: Dict[str, float] = {}

    def get_users(self) -> List[Dict[str, Any]]:
        return self.users

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        for u in self.users:
            if u["user_id"] == user_id:
                return u
        return None

    def generate_transaction(self, forced_fraud_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a single transaction event.
        Can be normal or injected with a specific fraud vector.
        """
        user = random.choice(self.users)
        user_id = user["user_id"]
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        is_fraud = forced_fraud_type is not None or (random.random() < self.fraud_probability)
        fraud_type = forced_fraud_type

        if is_fraud and not fraud_type:
            fraud_type = random.choice([
                "VELOCITY_BURST",
                "IMPOSSIBLE_TRAVEL",
                "SUDDEN_SPIKE",
                "CRYPTO_DRAIN",
                "MICRO_PROBE",
            ])

        if not is_fraud:
            # Normal user transaction
            category = random.choices(
                ["grocery", "dining", "digital_services", "travel", "electronics"],
                weights=[0.35, 0.35, 0.18, 0.08, 0.04],
            )[0]
            merchant_info = random.choice(MERCHANTS_BY_CATEGORY[category])
            merchant_name = merchant_info[0]

            # Generate amount near user's personal Gaussian spending curve
            amount = max(3.50, round(random.gauss(user["mean_amount"], user["std_amount"]), 2))
            
            # Normal location: near home with minor jitter
            loc = user["home_location"].copy()
            lat = round(loc["lat"] + random.uniform(-0.04, 0.04), 4)
            lon = round(loc["lon"] + random.uniform(-0.04, 0.04), 4)
            location = {
                "city": loc["city"],
                "country": loc["country"],
                "lat": lat,
                "lon": lon,
            }
            device_id = user["device_id"]
            fraud_type_label = None

        else:
            # Injected fraud vector scenarios
            fraud_type_label = fraud_type

            if fraud_type == "VELOCITY_BURST":
                # Rapid repeated transactions in electronics or digital
                category = "electronics"
                merchant_name = random.choice(MERCHANTS_BY_CATEGORY["electronics"])[0]
                amount = round(random.uniform(450.0, 1800.0), 2)
                loc = user["home_location"]
                location = {"city": loc["city"], "country": loc["country"], "lat": loc["lat"], "lon": loc["lon"]}
                device_id = user["device_id"]

            elif fraud_type == "IMPOSSIBLE_TRAVEL":
                # User transacting in a distant international continent within minutes
                category = random.choice(["luxury_goods", "electronics", "travel"])
                merchant_name = random.choice(MERCHANTS_BY_CATEGORY[category])[0]
                amount = round(random.uniform(600.0, 3200.0), 2)
                # Pick a city far away from user's home
                distant_cities = [c for c in CITIES if c["city"] != user["home_location"]["city"]]
                distant_loc = random.choice(distant_cities)
                location = {
                    "city": distant_loc["city"],
                    "country": distant_loc["country"],
                    "lat": distant_loc["lat"],
                    "lon": distant_loc["lon"],
                }
                device_id = f"DEV-ROGUE-{uuid.uuid4().hex[:6].upper()}"

            elif fraud_type == "SUDDEN_SPIKE":
                # An amount 20x to 50x user's baseline
                category = random.choice(["luxury_goods", "crypto"])
                merchant_name = random.choice(MERCHANTS_BY_CATEGORY[category])[0]
                amount = round(user["mean_amount"] * random.uniform(25.0, 65.0), 2)
                loc = user["home_location"]
                location = {"city": loc["city"], "country": loc["country"], "lat": loc["lat"], "lon": loc["lon"]}
                device_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"

            elif fraud_type == "CRYPTO_DRAIN":
                # Crypto transaction from an unrecognized device
                category = "crypto"
                merchant_name = random.choice(MERCHANTS_BY_CATEGORY["crypto"])[0]
                amount = round(random.uniform(1500.0, 5800.0), 2)
                loc = user["home_location"]
                location = {"city": loc["city"], "country": loc["country"], "lat": loc["lat"], "lon": loc["lon"]}
                device_id = f"DEV-ANON-{uuid.uuid4().hex[:6].upper()}"

            elif fraud_type == "MICRO_PROBE":
                # Card testing micro-transactions ($0.99 - $2.50)
                category = "digital_services"
                merchant_name = "Steam Games Store"
                amount = round(random.choice([0.99, 1.25, 1.99, 2.49]), 2)
                loc = user["home_location"]
                location = {"city": loc["city"], "country": loc["country"], "lat": loc["lat"], "lon": loc["lon"]}
                device_id = f"DEV-PROBE-{uuid.uuid4().hex[:6].upper()}"
            else:
                category = "electronics"
                merchant_name = "Best Buy Electronics"
                amount = 999.99
                location = user["home_location"]
                device_id = user["device_id"]

        self.last_user_tx_time[user_id] = now_ts

        return {
            "transaction_id": f"TXN-{random.randint(100000, 999999)}",
            "timestamp": now_iso,
            "epoch_time": now_ts,
            "user_id": user_id,
            "user_name": user["name"],
            "card_number": user["card_number"],
            "card_type": user["card_type"],
            "amount": amount,
            "currency": "USD",
            "merchant": merchant_name,
            "merchant_category": category,
            "location": location,
            "device_id": device_id,
            "is_simulated_ground_truth": is_fraud,
            "simulated_fraud_type": fraud_type_label,
        }
