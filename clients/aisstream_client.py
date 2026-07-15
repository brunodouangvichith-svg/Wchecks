"""
Client pour l'API AISstream.io (gratuite, clé requise), protocole WebSocket.

Mode "snapshot" : ouvre une connexion, s'abonne aux zones stratégiques
(config.STRATEGIC_ZONES), écoute pendant une fenêtre courte (config.AIS_SNAPSHOT_
DURATION_SECONDS), puis ferme la connexion et retourne les navires-citernes vus.

LIMITE IMPORTANTE (au-delà de celles déjà documentées dans le prompt de kickoff —
pas de cargaison, "going dark" possible) : AISstream ne permet pas de filtrer par
type de navire côté serveur. Le type de navire (ship_type) n'est transmis que par les
messages "ShipStaticData", envoyés beaucoup moins fréquemment que les messages de
position ("PositionReport"). Sur une fenêtre de 30-60s, beaucoup de navires visibles
en position n'auront pas encore émis leur ShipStaticData pendant la capture : ils sont
alors exclus du résultat (type inconnu), pas seulement les non-tankers. Le nombre de
tankers retourné est donc un SOUS-ENSEMBLE probable, pas un recensement exhaustif de
tous les tankers présents dans la zone à l'instant T.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

import config

logger = logging.getLogger(__name__)

WS_URL = "wss://stream.aisstream.io/v0/stream"


def _bounding_boxes() -> list:
    return [
        [[zone["lat_min"], zone["lon_min"]], [zone["lat_max"], zone["lon_max"]]]
        for zone in config.STRATEGIC_ZONES.values()
    ]


def _zone_for_position(lat: float, lon: float) -> str | None:
    for name, zone in config.STRATEGIC_ZONES.items():
        if zone["lat_min"] <= lat <= zone["lat_max"] and zone["lon_min"] <= lon <= zone["lon_max"]:
            return name
    return None


def _handle_message(message: dict, ship_types: dict, positions: dict) -> None:
    message_type = message.get("MessageType")
    mmsi = message.get("MetaData", {}).get("MMSI")
    if mmsi is None:
        return
    mmsi = str(mmsi)

    if message_type == "ShipStaticData":
        ship_type = message.get("Message", {}).get("ShipStaticData", {}).get("Type")
        if ship_type is not None:
            ship_types[mmsi] = ship_type
    elif message_type == "PositionReport":
        report = message.get("Message", {}).get("PositionReport", {})
        lat, lon = report.get("Latitude"), report.get("Longitude")
        if lat is None or lon is None:
            return
        positions[mmsi] = {
            "lat": lat,
            "lon": lon,
            "vitesse": report.get("Sog"),
            "cap": report.get("Cog"),
            "timestamp": message.get("MetaData", {}).get("time_utc")
            or datetime.now(timezone.utc).isoformat(),
        }


def _build_rows(ship_types: dict, positions: dict) -> list[dict]:
    rows = []
    for mmsi, pos in positions.items():
        ship_type = ship_types.get(mmsi)
        if ship_type not in config.AIS_TANKER_SHIP_TYPES:
            continue
        rows.append(
            {
                "mmsi": mmsi,
                "timestamp": pos["timestamp"],
                "lat": pos["lat"],
                "lon": pos["lon"],
                "vitesse": pos["vitesse"],
                "cap": pos["cap"],
                "zone_strategique": _zone_for_position(pos["lat"], pos["lon"]),
            }
        )
    return rows


async def _capture_snapshot(duration_seconds: int) -> list[dict]:
    if not config.AISSTREAM_API_KEY:
        raise RuntimeError(
            "AISSTREAM_API_KEY manquant : renseignez le fichier .env (voir .env.example). "
            "Clé gratuite : https://aisstream.io"
        )

    ship_types: dict[str, int] = {}
    positions: dict[str, dict] = {}

    subscribe_message = {
        "APIKey": config.AISSTREAM_API_KEY,
        "BoundingBoxes": _bounding_boxes(),
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(subscribe_message))
        try:
            async with asyncio.timeout(duration_seconds):
                async for raw_message in ws:
                    _handle_message(json.loads(raw_message), ship_types, positions)
        except TimeoutError:
            pass  # fin normale de la fenêtre de capture

    logger.info(
        "capture AISstream : %d navire(s) suivi(s), %d tanker(s) identifié(s)",
        len(positions), sum(1 for m in positions if ship_types.get(m) in config.AIS_TANKER_SHIP_TYPES),
    )
    return _build_rows(ship_types, positions)


def capture_tanker_snapshot(duration_seconds: int | None = None) -> list[dict]:
    """Point d'entrée synchrone (les collectors n'utilisent pas asyncio directement)."""
    duration = duration_seconds or config.AIS_SNAPSHOT_DURATION_SECONDS
    return asyncio.run(_capture_snapshot(duration))
