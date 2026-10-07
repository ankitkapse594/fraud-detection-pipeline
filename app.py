import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.generator import TransactionGenerator, USER_PROFILES
from engine.pipeline import FraudDetectionPipeline
from engine.rag_assistant import MarkdownRAGAssistant

app = FastAPI(title="Real-Time Fraud & Anomaly Detection Pipeline")

# Mount static directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Core Pipeline, Generator, and RAG Assistant Singletons
generator = TransactionGenerator(fraud_probability=0.08)
pipeline = FraudDetectionPipeline()
rag_assistant = MarkdownRAGAssistant(os.path.join(BASE_DIR, "README.md"))

# Streaming State
class StreamState:
    is_running: bool = True
    interval_seconds: float = 1.0  # Default 1 txn/sec
    connected_websockets: List[WebSocket] = []

stream_state = StreamState()


class StreamControlRequest(BaseModel):
    is_running: Optional[bool] = None
    tps: Optional[float] = None  # Transactions per second


class AttackRequest(BaseModel):
    attack_type: str  # VELOCITY_BURST, IMPOSSIBLE_TRAVEL, SUDDEN_SPIKE, CRYPTO_DRAIN, MICRO_PROBE


class ManualTransactionRequest(BaseModel):
    user_id: str
    amount: float
    merchant: str
    merchant_category: str
    city: str
    country: str
    lat: float
    lon: float
    is_new_device: bool = False


# Broadcast helper
async def broadcast_event(data: Dict[str, Any]):
    dead_connections = []
    message = json.dumps(data)
    for ws in stream_state.connected_websockets:
        try:
            await ws.send_text(message)
        except Exception:
            dead_connections.append(ws)
    
    for dead in dead_connections:
        if dead in stream_state.connected_websockets:
            stream_state.connected_websockets.remove(dead)


# Background streaming task
async def background_streamer():
    while True:
        if stream_state.is_running:
            try:
                raw_tx = generator.generate_transaction()
                enriched = pipeline.process_transaction(raw_tx)
                gold_summary = pipeline.medallion_store.get_gold_metrics()
                if len(stream_state.connected_websockets) > 0:
                    payload = {
                        "type": "TRANSACTION_EVENT",
                        "transaction": enriched,
                        "metrics": gold_summary,
                    }
                    await broadcast_event(payload)
            except Exception as e:
                print(f"[Streaming Error] {e}")

        await asyncio.sleep(stream_state.interval_seconds)


@app.on_event("startup")
async def startup_event():
    # Warm up pipeline with 20 initial transactions for rich initial metrics
    for _ in range(20):
        tx = generator.generate_transaction()
        pipeline.process_transaction(tx)
    # Start async streamer loop
    asyncio.create_task(background_streamer())


@app.get("/")
async def root():
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Fraud Detection API running. Please place index.html in templates/"}


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    stream_state.connected_websockets.append(websocket)

    # Send initial snapshot immediately upon connection
    initial_metrics = pipeline.medallion_store.get_gold_metrics()
    recent_transactions = pipeline.medallion_store.get_recent_silver_records(limit=15)
    await websocket.send_text(json.dumps({
        "type": "INITIAL_SNAPSHOT",
        "metrics": initial_metrics,
        "recent_transactions": recent_transactions,
        "stream_running": stream_state.is_running,
        "stream_interval": stream_state.interval_seconds,
    }))

    try:
        while True:
            # Keep-alive receive
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in stream_state.connected_websockets:
            stream_state.connected_websockets.remove(websocket)


@app.post("/api/stream/control")
async def control_stream(req: StreamControlRequest):
    if req.is_running is not None:
        stream_state.is_running = req.is_running
    if req.tps is not None and req.tps > 0:
        stream_state.interval_seconds = max(0.1, round(1.0 / req.tps, 2))
    
    return {
        "status": "success",
        "is_running": stream_state.is_running,
        "interval_seconds": stream_state.interval_seconds,
        "transactions_per_sec": round(1.0 / stream_state.interval_seconds, 2),
    }


@app.post("/api/simulate/attack")
async def inject_attack(req: AttackRequest):
    valid_attacks = {"VELOCITY_BURST", "IMPOSSIBLE_TRAVEL", "SUDDEN_SPIKE", "CRYPTO_DRAIN", "MICRO_PROBE"}
    if req.attack_type not in valid_attacks:
        raise HTTPException(status_code=400, detail=f"Invalid attack type. Choose from {valid_attacks}")

    results = []
    # If velocity burst, inject 4 transactions in rapid succession
    count = 4 if req.attack_type == "VELOCITY_BURST" else 1

    for _ in range(count):
        raw_tx = generator.generate_transaction(forced_fraud_type=req.attack_type)
        enriched = pipeline.process_transaction(raw_tx)
        results.append(enriched)
        # Broadcast immediately to UI
        gold_summary = pipeline.medallion_store.get_gold_metrics()
        await broadcast_event({
            "type": "TRANSACTION_EVENT",
            "transaction": enriched,
            "metrics": gold_summary,
            "is_injected_attack": True,
        })
        if count > 1:
            await asyncio.sleep(0.15)

    return {"status": "attack_injected", "count": len(results), "transactions": results}


@app.post("/api/transaction/test")
async def test_manual_transaction(req: ManualTransactionRequest):
    user = generator.get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    raw_tx = {
        "transaction_id": f"TEST-{os.urandom(3).hex().upper()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epoch_time": time.time(),
        "user_id": user["user_id"],
        "user_name": user["name"],
        "card_number": user["card_number"],
        "card_type": user["card_type"],
        "amount": req.amount,
        "currency": "USD",
        "merchant": req.merchant,
        "merchant_category": req.merchant_category,
        "location": {
            "city": req.city,
            "country": req.country,
            "lat": req.lat,
            "lon": req.lon,
        },
        "device_id": f"DEV-TEST-{os.urandom(2).hex()}" if req.is_new_device else user["device_id"],
        "is_simulated_ground_truth": False,
        "simulated_fraud_type": "MANUAL_SANDBOX_TEST",
    }

    enriched = pipeline.process_transaction(raw_tx)

    # Also broadcast to live feed so the user sees their sandbox test light up the UI
    gold_summary = pipeline.medallion_store.get_gold_metrics()
    await broadcast_event({
        "type": "TRANSACTION_EVENT",
        "transaction": enriched,
        "metrics": gold_summary,
        "is_sandbox_test": True,
    })

    return enriched


@app.get("/api/stream/latest")
async def get_latest_stream(limit: int = 20):
    return {
        "metrics": pipeline.medallion_store.get_gold_metrics(),
        "recent_transactions": pipeline.medallion_store.get_recent_silver_records(limit=limit),
    }


@app.get("/api/metrics")
async def get_metrics():
    return pipeline.medallion_store.get_gold_metrics()


@app.get("/api/users")
async def get_users():
    return generator.get_users()


@app.get("/api/user/{user_id}/features")
async def get_user_features(user_id: str):
    return pipeline.feature_store.get_user_state(user_id)


class ChatRequest(BaseModel):
    message: str


@app.post("/api/assistant/chat")
async def assistant_chat(req: ChatRequest):
    return rag_assistant.answer_query(req.message)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
