"""Porting di src/lib/osm/api.ts: creazione changeset/nodo su OpenStreetMap."""

import re

import requests

from app.services.osm_oauth import osm_server_url

CREATED_BY = "Fontanelle Italia (https://fontanelleitalia.com)"

POI_TAGS = {
    "fountain": {"amenity": "drinking_water"},
    "toilet": {"amenity": "toilets"},
    "bicycle_parking": {"amenity": "bicycle_parking"},
    "playground": {"leisure": "playground"},
}

CHANGESET_COMMENTS = {
    "fountain": "Add drinking fountain",
    "toilet": "Add public toilet",
    "bicycle_parking": "Add bicycle parking",
    "playground": "Add playground",
}

POI_TYPES = tuple(POI_TAGS.keys())


def is_poi_type(value) -> bool:
    return isinstance(value, str) and value in POI_TYPES


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _osm_request(access_token: str, method: str, path: str, body: str) -> str:
    response = requests.request(
        method,
        f"{osm_server_url()}{path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/xml",
        },
        data=body.encode("utf-8"),
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(
            f"OSM API {method} {path} failed with status {response.status_code}: {response.text}"
        )
    return response.text


def create_changeset(access_token: str, poi_type: str) -> int:
    comment = _xml_escape(CHANGESET_COMMENTS[poi_type])
    body = (
        "<osm><changeset>"
        f'<tag k="created_by" v="{_xml_escape(CREATED_BY)}"/>'
        f'<tag k="comment" v="{comment}"/>'
        "</changeset></osm>"
    )
    text = _osm_request(access_token, "PUT", "/api/0.6/changeset/create", body)
    if not re.fullmatch(r"\s*\d+\s*", text):
        raise RuntimeError(f"Changeset id non valido restituito da OSM: {text}")
    return int(text.strip())


def create_node(
    access_token: str, changeset_id: int, lat: float, lng: float, poi_type: str
) -> int:
    tags_xml = "".join(
        f'<tag k="{_xml_escape(k)}" v="{_xml_escape(v)}"/>'
        for k, v in POI_TAGS[poi_type].items()
    )
    body = (
        f'<osm><node changeset="{changeset_id}" lat="{lat}" lon="{lng}">'
        f"{tags_xml}</node></osm>"
    )
    text = _osm_request(access_token, "POST", "/api/0.6/nodes", body)
    if not re.fullmatch(r"\s*\d+\s*", text):
        raise RuntimeError(f"Node id non valido restituito da OSM: {text}")
    return int(text.strip())


def close_changeset(access_token: str, changeset_id: int) -> None:
    _osm_request(access_token, "PUT", f"/api/0.6/changeset/{changeset_id}/close", "")
