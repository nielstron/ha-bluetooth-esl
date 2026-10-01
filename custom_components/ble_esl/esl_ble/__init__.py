"""Protocol registry for BLE ESL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import (
    BATTERY_MAX_VOLTAGE,
    BATTERY_MIN_VOLTAGE,
    AdvertisementInfo,
    BleParser,
    Capabilities,
    DevicePreset,
    EslProtocol,
    ProtocolContractError,
    WriteResult,
)
from .easytag import EasyTagProtocol
from .etag import EtagProtocol
from .minew import MinewProtocol
from .picksmart import PickSmartProtocol
from .wolink import WolinkProtocol
from .xte import XteProtocol

if TYPE_CHECKING:
    from home_assistant_bluetooth import BluetoothServiceInfoBleak

_PROTOCOLS: dict[str, EslProtocol] = {}


def register(protocol: EslProtocol) -> None:
    """Register an ESL protocol (the class-level contract is checked at definition time)."""
    if protocol.id in _PROTOCOLS and _PROTOCOLS[protocol.id] is not protocol:
        raise ProtocolContractError(
            f"protocol id {protocol.id!r} is already registered by "
            f"{type(_PROTOCOLS[protocol.id]).__name__}"
        )
    _PROTOCOLS[protocol.id] = protocol


def get(protocol_id: str) -> EslProtocol:
    """Retrieve an ESL protocol by ID."""
    if protocol_id not in _PROTOCOLS:
        raise KeyError(
            f"Unknown BLE protocol: {protocol_id!r}. Available: {list(_PROTOCOLS.keys())}"
        )
    return _PROTOCOLS[protocol_id]


def all_protocols() -> list[EslProtocol]:
    """Return all registered ESL protocols."""
    return list(_PROTOCOLS.values())


def detect(
    service_info: BluetoothServiceInfoBleak,
) -> EslProtocol | None:
    """Detect matching BLE protocol from advertisement.

    Protocols are checked in registration order; protocols should define mutually
    exclusive supported() matchers to avoid ambiguous protocol resolution.
    """
    for protocol in _PROTOCOLS.values():
        if protocol.supported(service_info):
            return protocol
    return None


# Register standard protocols
register(WolinkProtocol())
register(EasyTagProtocol())
register(PickSmartProtocol())
register(XteProtocol())
register(EtagProtocol())
register(MinewProtocol())

__all__ = [
    "BATTERY_MAX_VOLTAGE",
    "BATTERY_MIN_VOLTAGE",
    "AdvertisementInfo",
    "BleParser",
    "Capabilities",
    "DevicePreset",
    "EasyTagProtocol",
    "EslProtocol",
    "PickSmartProtocol",
    "ProtocolContractError",
    "WolinkProtocol",
    "WriteResult",
    "XteProtocol",
    "all_protocols",
    "detect",
    "get",
    "register",
]
