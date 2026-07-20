"""Strict loader for the production-design-owned location continuity packages.

The package is the single textual spatial authority for every recurring location.
The matching catalog Scene-cast location master is the visual environment authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from story_video.asset_catalog import load_asset_catalog
from story_video.asset_support import StoryVideoError


PACKAGE_RELATIVE_PATH = (
    Path("direct-production-design") / "location-continuity-packages.json"
)
PACKAGE_CONTRACT = "location_continuity_packages/location-master-only"
ROOT_KEYS = {"contract", "path_resolution", "locations"}
LOCATION_KEYS = {
    "location_id",
    "scene_ids",
    "environment_state_en",
    "lighting_state_en",
    "palette_materials_en",
    "topology",
    "landmarks",
}
TOPOLOGY_KEYS = {
    "zones",
    "connections",
    "entrances_exits",
    "fixed_obstacles",
    "fixed_prop_placements",
}
ZONE_KEYS = {
    "zone_id",
    "description_en",
    "walkable",
    "capacity",
    "depth_affordance",
}
CONNECTION_KEYS = {
    "from_zone_id",
    "to_zone_id",
    "direction_en",
    "travel_seconds",
}
ACCESS_KEYS = {"access_id", "kind", "connected_zone_id", "direction_en"}
OBSTACLE_KEYS = {"obstacle_id", "zone_id", "description_en"}
PROP_PLACEMENT_KEYS = {
    "prop_id",
    "zone_id",
    "state_en",
    "interaction_points",
}
LANDMARK_KEYS = {
    "landmark_id",
    "zone_id",
    "kind",
    "description_en",
    "world_relationship_en",
}
DEPTH_VALUES = {"foreground", "midground", "background"}
ACCESS_KINDS = {"entrance", "exit", "both"}


class LocationContinuityError(StoryVideoError):
    """Raised when a location continuity package is missing or contradictory."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocationContinuityError(
            f"Missing location continuity package: {path}"
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocationContinuityError(
            f"Invalid UTF-8 JSON location continuity package: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise LocationContinuityError(
            "location-continuity-packages.json must contain one JSON object."
        )
    return payload


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise LocationContinuityError(
            f"{label} must use exact keys: {sorted(keys)}"
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocationContinuityError(f"{label} must be non-empty text.")
    return value.strip()


def _unique_texts(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise LocationContinuityError(f"{label} must be a string array.")
    result = [item.strip() for item in value]
    if len(result) != len(set(result)):
        raise LocationContinuityError(f"{label} must not repeat values.")
    return result


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise LocationContinuityError(f"{label} must be a number >= {minimum}.")
    return float(value)


def _validate_location(
    task_root: Path,
    raw: Any,
    *,
    assets: dict[str, Any],
) -> dict[str, Any]:
    location = _exact(raw, LOCATION_KEYS, "location continuity entry")
    location_id = _text(location["location_id"], "location_id")
    asset = assets.get(location_id)
    if not isinstance(asset, dict) or asset.get("type") != "location_master":
        raise LocationContinuityError(
            f"{location_id} must identify a current location_master asset."
        )
    scene_ids = _unique_texts(
        location["scene_ids"], f"{location_id}.scene_ids", allow_empty=False
    )
    topology = _exact(
        location["topology"], TOPOLOGY_KEYS, f"{location_id}.topology"
    )

    raw_zones = topology["zones"]
    if not isinstance(raw_zones, list) or not raw_zones:
        raise LocationContinuityError(f"{location_id}.topology.zones must be non-empty.")
    zones: list[dict[str, Any]] = []
    zone_ids: set[str] = set()
    for raw_zone in raw_zones:
        zone = _exact(raw_zone, ZONE_KEYS, f"{location_id} zone")
        zone_id = _text(zone["zone_id"], f"{location_id}.zone_id")
        if zone_id in zone_ids:
            raise LocationContinuityError(f"{location_id} repeats zone {zone_id}.")
        zone_ids.add(zone_id)
        if not isinstance(zone["walkable"], bool):
            raise LocationContinuityError(f"{location_id}/{zone_id}.walkable must be boolean.")
        depth = _text(zone["depth_affordance"], f"{location_id}/{zone_id}.depth")
        if depth not in DEPTH_VALUES:
            raise LocationContinuityError(f"{location_id}/{zone_id} has invalid depth.")
        zones.append(
            {
                "zone_id": zone_id,
                "description_en": _text(
                    zone["description_en"], f"{location_id}/{zone_id}.description"
                ),
                "walkable": zone["walkable"],
                "capacity": int(
                    _number(zone["capacity"], f"{location_id}/{zone_id}.capacity", minimum=1)
                ),
                "depth_affordance": depth,
            }
        )

    connections: list[dict[str, Any]] = []
    connection_ids: set[tuple[str, str]] = set()
    if not isinstance(topology["connections"], list):
        raise LocationContinuityError(f"{location_id}.connections must be an array.")
    for raw_connection in topology["connections"]:
        connection = _exact(raw_connection, CONNECTION_KEYS, f"{location_id} connection")
        source = _text(connection["from_zone_id"], f"{location_id}.from_zone_id")
        target = _text(connection["to_zone_id"], f"{location_id}.to_zone_id")
        if source not in zone_ids or target not in zone_ids or source == target:
            raise LocationContinuityError(
                f"{location_id} connection {source}->{target} is invalid."
            )
        pair = (source, target)
        if pair in connection_ids:
            raise LocationContinuityError(
                f"{location_id} repeats connection {source}->{target}."
            )
        connection_ids.add(pair)
        connections.append(
            {
                "from_zone_id": source,
                "to_zone_id": target,
                "direction_en": _text(
                    connection["direction_en"], f"{location_id}/{source}->{target}.direction"
                ),
                "travel_seconds": _number(
                    connection["travel_seconds"],
                    f"{location_id}/{source}->{target}.travel_seconds",
                    minimum=0.1,
                ),
            }
        )

    accesses: list[dict[str, str]] = []
    access_ids: set[str] = set()
    if not isinstance(topology["entrances_exits"], list):
        raise LocationContinuityError(f"{location_id}.entrances_exits must be an array.")
    for raw_access in topology["entrances_exits"]:
        access = _exact(raw_access, ACCESS_KEYS, f"{location_id} access")
        access_id = _text(access["access_id"], f"{location_id}.access_id")
        kind = _text(access["kind"], f"{location_id}/{access_id}.kind")
        zone_id = _text(
            access["connected_zone_id"], f"{location_id}/{access_id}.connected_zone_id"
        )
        if access_id in access_ids or kind not in ACCESS_KINDS or zone_id not in zone_ids:
            raise LocationContinuityError(f"{location_id} access {access_id} is invalid.")
        access_ids.add(access_id)
        accesses.append(
            {
                "access_id": access_id,
                "kind": kind,
                "connected_zone_id": zone_id,
                "direction_en": _text(
                    access["direction_en"], f"{location_id}/{access_id}.direction"
                ),
            }
        )

    obstacles: list[dict[str, str]] = []
    obstacle_ids: set[str] = set()
    if not isinstance(topology["fixed_obstacles"], list):
        raise LocationContinuityError(f"{location_id}.fixed_obstacles must be an array.")
    for raw_obstacle in topology["fixed_obstacles"]:
        obstacle = _exact(raw_obstacle, OBSTACLE_KEYS, f"{location_id} obstacle")
        obstacle_id = _text(obstacle["obstacle_id"], f"{location_id}.obstacle_id")
        zone_id = _text(obstacle["zone_id"], f"{location_id}/{obstacle_id}.zone_id")
        if obstacle_id in obstacle_ids or zone_id not in zone_ids:
            raise LocationContinuityError(
                f"{location_id} obstacle {obstacle_id} is invalid."
            )
        obstacle_ids.add(obstacle_id)
        obstacles.append(
            {
                "obstacle_id": obstacle_id,
                "zone_id": zone_id,
                "description_en": _text(
                    obstacle["description_en"],
                    f"{location_id}/{obstacle_id}.description",
                ),
            }
        )

    placements: list[dict[str, Any]] = []
    prop_ids: set[str] = set()
    approved_props = set(asset.get("included_prop_ids", []))
    if not isinstance(topology["fixed_prop_placements"], list):
        raise LocationContinuityError(
            f"{location_id}.fixed_prop_placements must be an array."
        )
    for raw_placement in topology["fixed_prop_placements"]:
        placement = _exact(
            raw_placement, PROP_PLACEMENT_KEYS, f"{location_id} prop placement"
        )
        prop_id = _text(placement["prop_id"], f"{location_id}.prop_id")
        zone_id = _text(placement["zone_id"], f"{location_id}/{prop_id}.zone_id")
        if prop_id in prop_ids or prop_id not in approved_props or zone_id not in zone_ids:
            raise LocationContinuityError(
                f"{location_id} fixed prop placement {prop_id} is invalid."
            )
        prop_ids.add(prop_id)
        placements.append(
            {
                "prop_id": prop_id,
                "zone_id": zone_id,
                "state_en": _text(
                    placement["state_en"], f"{location_id}/{prop_id}.state"
                ),
                "interaction_points": _unique_texts(
                    placement["interaction_points"],
                    f"{location_id}/{prop_id}.interaction_points",
                    allow_empty=False,
                ),
            }
        )

    raw_landmarks = location["landmarks"]
    if not isinstance(raw_landmarks, list) or not raw_landmarks:
        raise LocationContinuityError(f"{location_id}.landmarks must be non-empty.")
    landmarks: list[dict[str, str]] = []
    landmark_ids: set[str] = set()
    for raw_landmark in raw_landmarks:
        landmark = _exact(raw_landmark, LANDMARK_KEYS, f"{location_id} landmark")
        landmark_id = _text(landmark["landmark_id"], f"{location_id}.landmark_id")
        zone_id = _text(landmark["zone_id"], f"{location_id}/{landmark_id}.zone_id")
        if landmark_id in landmark_ids or zone_id not in zone_ids:
            raise LocationContinuityError(
                f"{location_id} landmark {landmark_id} is invalid."
            )
        landmark_ids.add(landmark_id)
        landmarks.append(
            {
                "landmark_id": landmark_id,
                "zone_id": zone_id,
                "kind": _text(landmark["kind"], f"{location_id}/{landmark_id}.kind"),
                "description_en": _text(
                    landmark["description_en"], f"{location_id}/{landmark_id}.description"
                ),
                "world_relationship_en": _text(
                    landmark["world_relationship_en"],
                    f"{location_id}/{landmark_id}.world_relationship",
                ),
            }
        )

    return {
        "location_id": location_id,
        "scene_ids": scene_ids,
        "scene_role_asset_ids": list(asset["included_role_asset_ids"]),
        "environment_state_en": _text(
            location["environment_state_en"], f"{location_id}.environment_state"
        ),
        "lighting_state_en": _text(
            location["lighting_state_en"], f"{location_id}.lighting_state"
        ),
        "palette_materials_en": _text(
            location["palette_materials_en"], f"{location_id}.palette_materials"
        ),
        "topology": {
            "zones": zones,
            "connections": connections,
            "entrances_exits": accesses,
            "fixed_obstacles": obstacles,
            "fixed_prop_placements": placements,
        },
        "landmarks": landmarks,
    }


def load_location_continuity_packages(task_root: Path) -> dict[str, Any]:
    """Load and validate the current task's complete location package."""

    root = task_root.expanduser().resolve(strict=True)
    payload = _exact(
        _load_json(root / PACKAGE_RELATIVE_PATH),
        ROOT_KEYS,
        "location-continuity-packages root",
    )
    if payload["contract"] != PACKAGE_CONTRACT:
        raise LocationContinuityError(
            f"location continuity contract must be {PACKAGE_CONTRACT!r}."
        )
    if payload["path_resolution"] != "task_root_relative":
        raise LocationContinuityError(
            "location continuity path_resolution must be task_root_relative."
        )
    catalog = load_asset_catalog(root)
    assets = catalog["assets"]
    raw_locations = payload["locations"]
    if not isinstance(raw_locations, list) or not raw_locations:
        raise LocationContinuityError("location continuity locations must be non-empty.")
    locations: list[dict[str, Any]] = []
    location_ids: set[str] = set()
    scene_ids: set[str] = set()
    for raw_location in raw_locations:
        location = _validate_location(root, raw_location, assets=assets)
        location_id = location["location_id"]
        if location_id in location_ids:
            raise LocationContinuityError(f"Duplicate location package {location_id}.")
        location_ids.add(location_id)
        overlap = scene_ids.intersection(location["scene_ids"])
        if overlap:
            raise LocationContinuityError(
                "Scenes may belong to exactly one location package; repeated: "
                + ", ".join(sorted(overlap))
            )
        scene_ids.update(location["scene_ids"])
        locations.append(location)
    expected_location_ids = {
        asset_id
        for asset_id, asset in assets.items()
        if isinstance(asset, dict) and asset.get("type") == "location_master"
    }
    if location_ids != expected_location_ids:
        raise LocationContinuityError(
            "Location packages must cover every location_master exactly once; "
            f"expected={sorted(expected_location_ids)}, actual={sorted(location_ids)}"
        )
    return {
        "contract": PACKAGE_CONTRACT,
        "path_resolution": "task_root_relative",
        "locations": locations,
    }


def location_models_by_id(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        location["location_id"]: location["topology"]
        for location in package["locations"]
    }


def location_continuity_authority_for_storyboard(
    storyboard: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    """Return compact topology while binding the one catalog location master."""

    scene_id = storyboard.get("scene_id")
    matches = [
        location
        for location in package.get("locations") or []
        if scene_id in location.get("scene_ids", [])
    ]
    if len(matches) != 1:
        raise LocationContinuityError(
            f"Storyboard {storyboard.get('segment_id')} must resolve one location package."
        )
    location = matches[0]
    return {
        "location_id": location["location_id"],
        "location_master_asset_id": location["location_id"],
        "scene_role_asset_ids": list(location["scene_role_asset_ids"]),
        "scene_id": scene_id,
        "reference_mode": "scene_cast_location_master_image_with_topology_text",
        "environment_state_en": location["environment_state_en"],
        "lighting_state_en": location["lighting_state_en"],
        "palette_materials_en": location["palette_materials_en"],
        "zone_ids": [zone["zone_id"] for zone in location["topology"]["zones"]],
        "landmark_relationships": {
            landmark["landmark_id"]: landmark["world_relationship_en"]
            for landmark in location["landmarks"]
        },
        "mirror_or_redesign_forbidden": True,
    }
