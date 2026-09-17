"""Ingestion API: receives telemetry from the client and publishes it to RabbitMQ (no DB persistence)."""
import json
import logging
import os

import pika
import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "telemetry_stream")

app = FastAPI(title="Sensor Ingest API")


class TelemetryPoint(BaseModel):
    """Single payload accepted from the client: no raw sensor data is forwarded to the server."""
    user_id: str
    session_id: str
    lat: float | None = None
    lon: float | None = None
    speed_kmh: float | None = None
    timestamp: float
    is_confirmed_fall: bool = False
    is_cancelled_fall: bool = False

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_user_id(cls, v):
        # Accept both string and number: some clients (e.g. tojson on an int)
        # may send user_id as a JSON number instead of a string.
        return str(v) if v is not None else v


class SessionEnd(BaseModel):
    """Signals the closure of a tracking session: triggers the GPX file close."""
    user_id: str
    session_id: str

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_user_id(cls, v):
        return str(v) if v is not None else v


class RabbitMQPublisher:
    """Persistent connection to RabbitMQ with automatic reconnection on error."""

    def __init__(self) -> None:
        self._connection: pika.BlockingConnection | None = None
        self._channel = None

    def _connect(self) -> None:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        params = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=30,
        )
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        logger.info("Connected to RabbitMQ (%s:%s), queue '%s' ready.", RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_QUEUE)

    def publish(self, body: bytes) -> None:
        if self._connection is None or self._connection.is_closed:
            self._connect()
        try:
            self._channel.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )
        except pika.exceptions.AMQPError:
            logger.warning("RabbitMQ connection lost, reconnecting...")
            self._connect()
            self._channel.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )


publisher = RabbitMQPublisher()


def verify_flask_session(request: Request):
    """Verifies the Flask session cookie by calling the internal auth endpoint."""
    cookies = request.headers.get("cookie", "")
    try:
        cookie_dict = {}
        for part in cookies.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookie_dict[k] = v
        session_cookie = cookie_dict.get("session")
        resp = requests.get(
            "http://web:8000/auth/check_session",
            cookies={"session": session_cookie} if session_cookie else {},
            timeout=2,
        )
        if resp.status_code == 200 and resp.json().get("authenticated"):
            return resp.json()
    except Exception:  # noqa: BLE001
        logger.debug("Failed to verify Flask session cookie")
    raise HTTPException(status_code=401, detail="Invalid or missing session")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/stream")
def handle_stream(points: list[TelemetryPoint], request: Request):
    session = verify_flask_session(request)
    if not points:
        return {"status": "ok", "count": 0}

    auth_user_id = str(session.get("user_id"))

    try:
        for point in points:
            # Bind payload to the authenticated session user (prevent impersonation)
            envelope = {"type": "point", "user_id": auth_user_id, **point.model_dump(exclude={"user_id"})}
            envelope["user_id"] = auth_user_id
            publisher.publish(json.dumps(envelope).encode("utf-8"))
    except Exception as exc:
        logger.error("Error publishing to RabbitMQ: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to forward data to RabbitMQ") from exc

    return {"status": "ok", "count": len(points)}


@app.post("/session/end")
def handle_session_end(payload: SessionEnd, request: Request):
    session = verify_flask_session(request)
    """Signals the GPS worker to close the buffer, apply RDP and export the final .gpx file."""
    auth_user_id = str(session.get("user_id"))
    try:
        envelope = {"type": "session_end", "user_id": auth_user_id, **payload.model_dump(exclude={"user_id"})}
        envelope["user_id"] = auth_user_id
        publisher.publish(json.dumps(envelope).encode("utf-8"))
    except Exception as exc:
        logger.error("Error publishing session end to RabbitMQ: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to forward session end to RabbitMQ") from exc

    return {"status": "ok"}# Endpoint bicycle_repair (aggiungere): @app.get("/api/v1/bicycle_repair") def get_repair(): ...
