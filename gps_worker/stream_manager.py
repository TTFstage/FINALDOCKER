"""Gestione dello streaming append-only dei punti GPS e produzione del file .gpx finale."""
import logging
import math
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from rdp_optimizer import ramer_douglas_peucker

logger = logging.getLogger(__name__)

Point = tuple[float, float, float | None, float]  # lat, lon, elev, timestamp_ms


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _iso_from_epoch_ms(ts_ms: float) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()


class GPXStreamManager:
    """Buffer RAM per-sessione + append-only su disco, con export .gpx compresso via RDP alla chiusura."""

    def __init__(self, output_base_dir: str, buffer_size: int = 50) -> None:
        self.output_base_dir = output_base_dir
        self.buffer_size = buffer_size
        os.makedirs(self.output_base_dir, exist_ok=True)
        self._buffers: dict[tuple[str, str], list[Point]] = {}

    def _tmp_path(self, user_id: str, session_id: str) -> str:
        return os.path.join(self.output_base_dir, f"{user_id}_{session_id}.gpx.tmp")

    def _final_path(self, user_id: str, session_id: str) -> str:
        return os.path.join(self.output_base_dir, f"{user_id}_{session_id}.gpx")

    def add_point(
        self,
        session_id: str,
        user_id: str,
        lat: float | None,
        lon: float | None,
        elev: float | None,
        timestamp: float,
    ) -> None:
        # Scarta i punti senza fix GPS valida (lat/lon nulli, es. primi campioni
        # prima che watchPosition restituisca la prima posizione): un valore
        # None scritto su disco romperebbe il parsing in _read_points.
        if lat is None or lon is None:
            logger.debug(
                "Punto scartato per coordinate mancanti (user=%s session=%s)", user_id, session_id
            )
            return

        key = (user_id, session_id)
        buffer = self._buffers.setdefault(key, [])
        buffer.append((lat, lon, elev, timestamp))
        if len(buffer) >= self.buffer_size:
            self._flush(key)

    def _flush(self, key: tuple[str, str]) -> None:
        buffer = self._buffers.get(key)
        if not buffer:
            return
        user_id, session_id = key
        with open(self._tmp_path(user_id, session_id), "a", encoding="utf-8") as fh:
            fh.writelines(f"{lat},{lon},{'' if elev is None else elev},{timestamp}\n" for lat, lon, elev, timestamp in buffer)
        self._buffers[key] = []

    def _read_points(self, user_id: str, session_id: str) -> list[Point]:
        tmp_path = self._tmp_path(user_id, session_id)
        points: list[Point] = []
        if not os.path.exists(tmp_path):
            return points
        with open(tmp_path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    lat_s, lon_s, elev_s, ts_s = line.split(",")
                    points.append((float(lat_s), float(lon_s), float(elev_s) if elev_s else None, float(ts_s)))
                except ValueError:
                    # Riga corrotta (es. valori 'None' scritti da versioni precedenti
                    # del worker): la scartiamo invece di far fallire l'intera sessione.
                    logger.warning(
                        "Riga %d non valida in %s, scartata: %r", line_no, tmp_path, line
                    )
        return points

    def close_session(
        self,
        session_id: str,
        user_id: str,
        apply_rdp: bool = True,
        epsilon: float = 0.00004,
    ) -> tuple[str, float, float] | None:
        key = (user_id, session_id)
        self._flush(key)
        self._buffers.pop(key, None)

        points = self._read_points(user_id, session_id)
        if not points:
            logger.warning("Nessun punto per user=%s session=%s, nessun .gpx generato.", user_id, session_id)
            return None

        if apply_rdp and len(points) >= 3:
            points = ramer_douglas_peucker(points, epsilon)

        final_path = self._final_path(user_id, session_id)
        self._write_gpx(points, final_path)

        tmp_path = self._tmp_path(user_id, session_id)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        total_distance_km = sum(
            _haversine_km(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
            for i in range(len(points) - 1)
        )
        duration_min = (points[-1][3] - points[0][3]) / 60000.0 if len(points) > 1 else 0.0

        logger.info(
            "Sessione chiusa: user=%s session=%s punti=%d distanza_km=%.3f durata_min=%.1f -> %s",
            user_id, session_id, len(points), total_distance_km, duration_min, final_path,
        )
        return final_path, total_distance_km, duration_min

    @staticmethod
    def _write_gpx(points: list[Point], final_path: str) -> None:
        root = ET.Element("gpx", version="1.1", creator="sensor-app-gps-worker")
        trk = ET.SubElement(root, "trk")
        trkseg = ET.SubElement(trk, "trkseg")
        for lat, lon, elev, timestamp in points:
            trkpt = ET.SubElement(trkseg, "trkpt", lat=repr(lat), lon=repr(lon))
            if elev is not None:
                ET.SubElement(trkpt, "ele").text = repr(elev)
            ET.SubElement(trkpt, "time").text = _iso_from_epoch_ms(timestamp)
        ET.ElementTree(root).write(final_path, encoding="utf-8", xml_declaration=True)
