"""API di ingestion: riceve la telemetria dal client e la pubblica su RabbitMQ (nessuna persistenza su DB)."""
import json
import logging
import os

import pika
from fastapi import FastAPI, HTTPException
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
    """Unico payload accettato dal client: nessun dato grezzo dei sensori viene inoltrato al server."""
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
        # Accetta sia stringa che numero: alcuni client (es. tojson su un int)
        # possono inviare user_id come JSON number invece che come stringa.
        return str(v) if v is not None else v


class SessionEnd(BaseModel):
    """Segnala la chiusura di un turno di tracciamento: fa scattare la chiusura del file GPX."""
    user_id: str
    session_id: str

    @field_validator("user_id", mode="before")
    @classmethod
    def _coerce_user_id(cls, v):
        return str(v) if v is not None else v


class RabbitMQPublisher:
    """Connessione persistente verso RabbitMQ con riconnessione automatica in caso di errore."""

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
        logger.info("Connesso a RabbitMQ (%s:%s), coda '%s' pronta.", RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_QUEUE)

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
            logger.warning("Connessione RabbitMQ persa, riconnessione in corso...")
            self._connect()
            self._channel.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )


publisher = RabbitMQPublisher()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/stream")
def handle_stream(points: list[TelemetryPoint]):
    if not points:
        return {"status": "ok", "count": 0}

    try:
        for point in points:
            envelope = {"type": "point", **point.model_dump()}
            publisher.publish(json.dumps(envelope).encode("utf-8"))
    except Exception as exc:
        logger.error("Errore pubblicazione su RabbitMQ: %s", exc)
        raise HTTPException(status_code=503, detail="Impossibile inoltrare i dati a RabbitMQ") from exc

    return {"status": "ok", "count": len(points)}


@app.post("/session/end")
def handle_session_end(payload: SessionEnd):
    """Segnala al worker GPS di chiudere il buffer, applicare RDP ed esportare il file .gpx finale."""
    try:
        envelope = {"type": "session_end", **payload.model_dump()}
        publisher.publish(json.dumps(envelope).encode("utf-8"))
    except Exception as exc:
        logger.error("Errore pubblicazione fine sessione su RabbitMQ: %s", exc)
        raise HTTPException(status_code=503, detail="Impossibile inoltrare la chiusura sessione a RabbitMQ") from exc

    return {"status": "ok"}