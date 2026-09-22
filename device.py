"""Inkbird IBBQ-4T device polling via tinytuya.

Handles both firmware variants:
- V1: probes 1-4 in separate DPSes 107, 108, 109, 110 (integer, value / 100)
- V2: all 4 probes packed in DPS 107 as base64-encoded 16 bytes
      (4x little-endian uint32, each / 100)

Unplugged probes return sentinel values (e.g. 6552); we filter anything
above a plausibility threshold to None.
"""
import base64
import struct
from typing import Optional, TypedDict

import tinytuya

# Anything above this is implausible (max usable smoker temp ~600F).
# V1 firmware reports 0xFFF0 / 100 = 655.2 for unplugged probes, so 600 filters those.
TEMP_PLAUSIBLE_MAX = 600.0


class Reading(TypedDict):
    probes: list[Optional[float]]
    battery: Optional[int]
    powered_on: Optional[bool]
    unit: str


def _plausible(temp: float) -> Optional[float]:
    return temp if 0 < temp < TEMP_PLAUSIBLE_MAX else None


def _decode_v1(dps: dict) -> list[Optional[float]]:
    """V1 firmware: separate DPSes per probe."""
    probes: list[Optional[float]] = []
    for dps_id in ("107", "108", "109", "110"):
        raw = dps.get(dps_id)
        if raw is None:
            probes.append(None)
        else:
            probes.append(_plausible(raw / 100))
    return probes


def _decode_v2(dps: dict) -> list[Optional[float]]:
    """V2 firmware: 4 probes in base64-encoded DPS 107.

    Each probe occupies 4 bytes: little-endian uint16 temperature (x100),
    followed by a 2-byte status word. Confirmed from community packet captures.
    """
    raw = dps.get("107")
    if not isinstance(raw, str):
        return [None] * 4
    data = base64.b64decode(raw)
    if len(data) < 16:
        return [None] * 4
    probes: list[Optional[float]] = []
    for i in range(0, 16, 4):
        temp_raw = struct.unpack("<H", data[i:i + 2])[0]
        probes.append(_plausible(temp_raw / 100))
    return probes


def read_status(device_id: str, ip: str, local_key: str, version: float) -> Reading:
    """Synchronous tinytuya call. Wrap in asyncio.to_thread from async code."""
    d = tinytuya.OutletDevice(
        dev_id=device_id,
        address=ip,
        local_key=local_key,
        version=version,
    )
    data = d.status()
    if "dps" not in data:
        raise RuntimeError(f"Bad response from device: {data!r}")

    dps = data["dps"]

    # Detect firmware variant by inspecting DPS 107 type
    if isinstance(dps.get("107"), str):
        probes = _decode_v2(dps)
    else:
        probes = _decode_v1(dps)

    unit = dps.get("19", "F")
    if isinstance(unit, str):
        unit = unit.upper()

    return Reading(
        probes=probes,
        battery=dps.get("101"),
        powered_on=dps.get("1"),
        unit=unit,
    )
