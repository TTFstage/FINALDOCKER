"""RabbitMQ Consumer: feeds the GPXStreamManager and records track metadata to PostgreSQL."""
import json
import logging
import os
import time

import pika
import psycopg
from stream_manager import GPXStreamManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "telemetry_stream")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "sensor_app")
DB_USER = os.getenv("DB_USER", "sensor_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sensor_app")

OUTPUT_BASE_DIR = os.getenv("OUTPUT_BASE_DIR", "/data/volume_gpx_storage")
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "50"))
RDP_EPSILON = float(os.getenv("RDP_EPSILON", "0.00004"))

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
POSITION_TTL = int(os.getenv("POSITION_TTL", "90"))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

stream_mgr = GPXStreamManager(output_base_dir=OUTPUT_BASE_DIR, buffer_size=BUFFER_SIZE)


def get_db_conn():
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def save_shift_metadata(session_id: str, user_id: str, gpx_path: str, distance_km: float, duration_min: float) -> None:
    try:
        with get_db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rider_shifts (session_id, user_id, gpx_path, total_distance_km, duration_min)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, user_id, gpx_path, distance_km, duration_min),
            )
    except Exception:
        logger.exception("Error saving shift metadata to Postgres (user=%s session=%s)", user_id, session_id)


def save_fall_event(session_id: str, user_id: str, lat: float | None, lon: float | None, timestamp_ms: float) -> None:
    """Persists a confirmed fall to Postgres (table fall_events)."""
    if lat is None or lon is None:
        logger.warning(
            "Confirmed fall without valid GPS coordinates, not saved (user=%s session=%s)",
            user_id, session_id,
        )
        return
    try:
        with get_db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fall_events (session_id, user_id, latitude, longitude, "timestamp")
                VALUES (%s, %s, %s, %s, to_timestamp(%s))
                """,
                (session_id, user_id, lat, lon, timestamp_ms / 1000.0),
            )
    except Exception:
        logger.exception("Error saving fall to Postgres (user=%s session=%s)", user_id, session_id)


def on_message(channel, method, properties, body: bytes) -> None:
    try:
        envelope = json.loads(body)
        msg_type = envelope.get("type")

        if msg_type == "point":
            stream_mgr.add_point(
                session_id=envelope["session_id"],
                user_id=envelope["user_id"],
                lat=envelope.get("lat"),
                lon=envelope.get("lon"),
                elev=None,
                timestamp=envelope["timestamp"],
            )
            if envelope.get("lat") is not None and envelope.get("lon") is not None:
            # user_id matches user_id (solution 1)
                redis_client.set(
                    f"position:{envelope['user_id']}",
                    json.dumps({
                        "lat": envelope["lat"],
                        "lon": envelope["lon"],
                        "session_id": envelope["session_id"],
                        "ts": envelope["timestamp"],
                    }),
                    ex=POSITION_TTL,
                )
            if envelope.get("is_confirmed_fall"):
                save_fall_event(
                    session_id=envelope["session_id"],
                    user_id=envelope["user_id"],
                    lat=envelope.get("lat"),
                    lon=envelope.get("lon"),
                    timestamp_ms=envelope["timestamp"],
                )
        elif msg_type == "session_end":
            result = stream_mgr.close_session(
                session_id=envelope["session_id"],
                user_id=envelope["user_id"],
                apply_rdp=True,
                epsilon=RDP_EPSILON,
            )
            if result is not None:
                final_path, distance_km, duration_min = result
                save_shift_metadata(envelope["session_id"], envelope["user_id"], final_path, distance_km, duration_min)
        else:
            logger.warning("Message with unknown type ignored: %s", msg_type)

    except Exception:
        logger.exception("Error processing message, it will be acknowledged anyway (no critical data loss).")
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials, heartbeat=30
    )

    while True:
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=20)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=on_message)

            logger.info("GPS Worker listening on queue '%s'...", RABBITMQ_QUEUE)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logger.warning("RabbitMQ unreachable, retrying in 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Interrupt requested, shutting down worker.")
            break


if __name__ == "__main__":
    run()