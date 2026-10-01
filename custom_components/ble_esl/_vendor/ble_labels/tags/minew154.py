"""Minew MTag15 200x200 BWRY discovery and connection; image writes pending."""

import asyncio
from contextlib import asynccontextmanager
import sys

from bleak import BleakClient, BleakScanner
from PIL import Image

from .base import DiscoveredTag, TagConnection, TagDriver

COMPANY_ID = 0x0639
SERVICE = "7f280001-8204-f393-e0a9-e50e24dcca9e"
CHARACTERISTIC = "7f280003-8204-f393-e0a9-e50e24dcca9e"
SCREEN_ID = 65
SIZE = (200, 200)
PALETTE = ((0, 0, 0), (255, 255, 255), (255, 0, 0), (255, 255, 0))


def device_info(advertisement):
    """Decode CA00 identification frames; CA21 status frames have no tag ID."""
    payload = advertisement.manufacturer_data.get(COMPANY_ID)
    if payload is None or payload[:2] != b"\xca\x00":
        return None
    if len(payload) != 24:
        raise ValueError(f"Expected a 24-byte Minew CA00 frame, got {len(payload)}")
    firmware = int.from_bytes(payload[9:11], "big")
    fields = int.from_bytes(payload[11:19], "big")
    return {
        "id": payload[2:8][::-1].hex().upper(),
        "battery_percent": payload[8],
        "firmware": f"{firmware >> 13}.{(firmware >> 7) & 63}.{firmware & 127}",
        "screen_id": (fields >> 16) & 0xFFF,
        "product_id": f"{(fields >> 28) & 0xFFFF:04x}",
    }


def scanner_options():
    """Use CoreBluetooth address lookup only on macOS."""
    return {"cb": {"use_bdaddr": True}} if sys.platform == "darwin" else {}


async def discover(seconds):
    found = {}

    def detected(device, advertisement):
        payload = advertisement.manufacturer_data.get(COMPANY_ID)
        if payload is None or payload[:1] != b"\xca":
            return
        info = device_info(advertisement)
        if info is not None and info["screen_id"] != SCREEN_ID:
            return
        identifier = device.address.replace(":", "").upper()
        if info is None:
            info = found[identifier][2] if identifier in found else {"id": identifier}
        found[identifier] = (device, advertisement.rssi, info)

    # Bleak's optional macOS address lookup also identifies CA21 status frames.
    # Verified on this Mac; it uses a private CoreBluetooth API.
    async with BleakScanner(detected, **scanner_options()):
        await asyncio.sleep(seconds)
    return found


class MinewConnection(TagConnection):
    def __init__(self, client, metadata):
        self.client = client
        self.metadata = metadata

    async def info(self):
        return {
            **self.metadata,
            "configured_size": SIZE,
            "configured_colors": "black/white/red/yellow",
            "authenticated": False,
            "image_writes_supported": False,
            "services": [
                {
                    "service": service.uuid,
                    "characteristic": char.uuid,
                    "properties": char.properties,
                }
                for service in self.client.services
                for char in service.characteristics
            ],
        }

    async def write(self, image, *, timeout, log, progress):
        raise NotImplementedError(
            "Minew discovery and connection work; authentication and image writes are not yet verified"
        )


class Minew154Driver(TagDriver):
    writable = False
    name = "minew154"
    description = "Minew MTag15 BWRY (experimental; scan/info only)"
    size = SIZE
    palette = PALETTE

    async def scan(self, seconds):
        return [
            DiscoveredTag(f"Minew-{info['id']}", device.address, rssi)
            for device, rssi, info in (await discover(seconds)).values()
        ]

    @asynccontextmanager
    async def connect(self, identifier):
        requested = identifier.upper().removeprefix("MINEW-").replace(":", "")
        matched = None

        def match(device, advertisement):
            nonlocal matched
            payload = advertisement.manufacturer_data.get(COMPANY_ID)
            if payload is None or payload[:1] != b"\xca":
                return False
            info = device_info(advertisement)
            identifier = device.address.replace(":", "").upper()
            identifiers = {identifier}
            if sys.platform == "darwin":
                identifiers.add(
                    str(advertisement.platform_data[0].identifier().UUIDString()).upper()
                )
            if info is not None:
                identifiers.add(info["id"])
            if requested not in identifiers:
                return False
            if info is not None and info["screen_id"] != SCREEN_ID:
                raise ValueError(
                    f"Minew screen ID {info['screen_id']} is not supported by minew154"
                )
            matched = info or {"id": identifier}
            return True

        device = await BleakScanner.find_device_by_filter(match, timeout=60, **scanner_options())
        if device is None:
            raise RuntimeError(f"No advertisement from Minew tag {identifier} within 60 seconds")
        async with BleakClient(device, timeout=20) as client:
            service = client.services.get_service(SERVICE)
            if service is None or service.get_characteristic(CHARACTERISTIC) is None:
                raise ValueError(
                    "Tag does not expose the Minew tagble_v3 service and characteristic"
                )
            yield MinewConnection(client, matched)

    def prepare_image(self, image):
        if image.size != SIZE:
            raise ValueError(f"Expected {SIZE[0]} x {SIZE[1]} image, got {image.size}")
        rgba = Image.new("RGBA", SIZE, "white")
        rgba.alpha_composite(image.convert("RGBA"))
        palette = Image.new("P", (1, 1))
        palette.putpalette(list(sum(PALETTE, ())) * 64)
        return (
            rgba.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
        )
