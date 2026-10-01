"""FFE0/FFE1 ETAG 2.13-inch BWR protocol, verified on 52500058B6."""

import asyncio
from contextlib import asynccontextmanager
import struct

from bleak import BleakClient, BleakScanner
from PIL import Image

from .base import DiscoveredTag, TagConnection, TagDriver

SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC = "0000ffe1-0000-1000-8000-00805f9b34fb"
FIRMWARE = "00002a26-0000-1000-8000-00805f9b34fb"
SIZE = (250, 122)
PALETTE = ((0, 0, 0), (255, 255, 255), (255, 0, 0))


def quantize(image):
    if image.size != SIZE:
        raise ValueError(f"Expected {SIZE[0]} x {SIZE[1]} image, got {image.size}")
    rgba = image.convert("RGBA")
    rgb = Image.new("RGBA", SIZE, "white")
    rgb.alpha_composite(rgba)
    palette = Image.new("P", (1, 1))
    palette.putpalette(list(sum(PALETTE, ())) * 85 + [0, 0, 0])
    return rgb.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")


def encode(image, firmware):
    """APK a2.c.f/g/h: two MSB-first planes, padded per column."""
    image = quantize(image)
    black, red = bytearray(), bytearray()
    reverse = "SE0213MN50-TNG-A0" in firmware
    xs = range(249, -1, -1) if reverse else range(250)
    for x in xs:
        colors = [image.getpixel((x, y)) for y in (range(121, -1, -1) if reverse else range(122))]
        if not reverse:
            colors = [PALETTE[0]] * 6 + colors
        for start in range(0, len(colors), 8):
            bw, accent = 255, 0
            for bit, color in enumerate(colors[start : start + 8]):
                if color == PALETTE[0]:
                    bw &= ~(128 >> bit)
                elif color == PALETTE[2]:
                    accent |= 128 >> bit
            black.append(bw)
            red.append(accent)
    return bytes(black), bytes(red)


def packets(image, firmware):
    # APK SendPublishTemplateActivity.h2, type 1. These are app commands,
    # not Bluetooth pairing or firmware flashing.
    yield bytes.fromhex("ac05ca")
    yield bytes.fromhex("ac1100112233445566778899112233445566ca")
    yield bytes.fromhex("ac07ca")
    for plane, data in enumerate(encode(image, firmware)):
        count = (len(data) + 229) // 230
        for index in range(count):
            chunk = data[index * 230 : (index + 1) * 230]
            yield struct.pack(">BBBHHH", 0xAC, 1, plane, index, count, len(chunk)) + chunk + b"\xca"
    yield bytes.fromhex("ac03ca")


async def find_device(identifier):
    device = await BleakScanner.find_device_by_filter(
        lambda d, a: (
            identifier.upper()
            in {
                d.address.upper(),
                (a.local_name or d.name or "").upper(),
                (a.local_name or d.name or "").upper().removeprefix("ETAG-"),
            }
        ),
        timeout=15,
    )
    if device is None:
        raise RuntimeError(
            f"Tag {identifier} not found; close the phone app and move the tag nearby"
        )
    return device


class EtagConnection(TagConnection):
    def __init__(self, client, firmware):
        self.client = client
        self.firmware = firmware

    async def info(self):
        return {
            "firmware": self.firmware,
            "size": SIZE,
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
        image = quantize(image)
        char = self.client.services.get_service(SERVICE).get_characteristic(CHARACTERISTIC)
        outgoing = list(packets(image, self.firmware))
        if char.max_write_without_response_size < max(map(len, outgoing)):
            raise ValueError("Bluetooth write size is too small for the app's 240-byte packets")
        queue = asyncio.Queue()

        def notification(_, data):
            raw = bytes(data)
            log.append({"rx": raw.hex()})
            queue.put_nowait(raw)

        await self.client.start_notify(char, notification)
        for n, packet in enumerate(outgoing, 1):
            log.append({"tx": packet.hex()})
            await self.client.write_gatt_char(char, packet, response=False)
            reply = await asyncio.wait_for(queue.get(), timeout=timeout)
            if not (reply.startswith(b"\x91") and reply.endswith(b"\x19")):
                raise RuntimeError(f"Unexpected response: {reply.hex()}")
            command = packet[1]
            expected = {5: 6, 0x11: 0x12, 7: 8, 1: 2, 3: 4}[command]
            if reply[1] != expected:
                raise RuntimeError(f"Expected response {expected:02x}, got {reply.hex()}")
            if command == 1:
                if (
                    int.from_bytes(reply[2:4], "little") != int.from_bytes(packet[3:5], "big")
                    or reply[4] != 0
                ):
                    raise RuntimeError(f"Image packet rejected: {reply.hex()}")
            elif command != 7 and reply[2] != 0:
                raise RuntimeError(f"Command rejected: {reply.hex()}")
            progress(n, len(outgoing))
        await asyncio.sleep(1)


class Etag213Driver(TagDriver):
    name = "etag213"
    description = "ETAG 2.13-inch black/white/red (FFE0/FFE1)"
    size = SIZE
    palette = PALETTE

    async def scan(self, seconds):
        devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
        return [
            DiscoveredTag(adv.local_name or device.name or "", device.address, adv.rssi)
            for device, adv in devices.values()
            if (adv.local_name or device.name or "").startswith("ETAG")
        ]

    @asynccontextmanager
    async def connect(self, identifier):
        async with BleakClient(await find_device(identifier)) as client:
            firmware = (await client.read_gatt_char(FIRMWARE)).decode()
            if not any(panel in firmware for panel in ("SE0213NP61-TNG-A0", "SE0213MN50-TNG-A0")):
                raise ValueError(f"Unsupported panel firmware: {firmware}")
            service = client.services.get_service(SERVICE)
            if service is None or service.get_characteristic(CHARACTERISTIC) is None:
                raise ValueError("Tag does not expose the ETAG FFE0/FFE1 protocol")
            yield EtagConnection(client, firmware)

    def prepare_image(self, image):
        return quantize(image)
