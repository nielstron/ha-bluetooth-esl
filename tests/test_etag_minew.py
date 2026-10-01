"""New protocol discovery and ETAG acknowledged packet transfer."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from custom_components.ble_esl import esl_ble
from custom_components.ble_esl._vendor.ble_labels.tags.etag213 import (
    EtagConnection,
    encode,
    packets,
)
from custom_components.ble_esl.esl_ble.base import WriteRefused


def test_etag_discovery_and_padding():
    info = SimpleNamespace(name="ETAG-52500058B6", manufacturer_data={}, service_uuids=[])
    protocol = esl_ble.detect(info)
    assert protocol.id == "etag"
    assert protocol.preset_for(None).height == 122
    image = Image.new("RGB", (250, 122), "white")
    black, red = encode(image, "SE0213NP61-TNG-A0")
    assert len(black) == len(red) == 4000
    assert black[:16] == b"\x03" + b"\xff" * 15
    assert red == b"\x00" * 4000
    assert len(list(packets(image, "SE0213NP61-TNG-A0"))) == 40


@pytest.mark.parametrize("rejected", [False, True])
async def test_transfer_checks_acknowledgements(rejected):
    callback = None
    char = SimpleNamespace(max_write_without_response_size=244)
    service = SimpleNamespace(get_characteristic=lambda uuid: char)
    client = SimpleNamespace(services=SimpleNamespace(get_service=lambda uuid: service))

    async def start_notify(characteristic, fn):
        nonlocal callback
        callback = fn

    async def write_gatt_char(characteristic, packet, response):
        command = packet[1]
        reply_command = {5: 6, 0x11: 0x12, 7: 8, 1: 2, 3: 4}[command]
        if command == 1:
            index = int.from_bytes(packet[3:5], "big")
            reply = b"\x91\x02" + index.to_bytes(2, "little") + bytes([int(rejected)]) + b"\x19"
        else:
            reply = bytes([0x91, reply_command, 0, 0x19])
        callback(char, reply)

    client.start_notify = start_notify
    client.write_gatt_char = AsyncMock(side_effect=write_gatt_char)
    progress = []
    connection = EtagConnection(client, "SE0213NP61-TNG-A0")
    if rejected:
        with pytest.raises(RuntimeError, match="rejected"):
            await connection.write(
                Image.new("RGB", (250, 122), "white"),
                timeout=1,
                log=[],
                progress=lambda n, total: progress.append(n),
            )
    else:
        await connection.write(
            Image.new("RGB", (250, 122), "white"),
            timeout=1,
            log=[],
            progress=lambda n, total: progress.append(n),
        )
        assert progress == list(range(1, 41))


async def test_minew_is_explicitly_discovery_only():
    info = SimpleNamespace(name="", manufacturer_data={0x0639: b"\xca\x21"}, service_uuids=[])
    protocol = esl_ble.detect(info)
    assert protocol.id == "minew"
    assert protocol.writable is False
    with pytest.raises(WriteRefused, match="not yet verified"):
        await protocol.write_prepared(None, None, None)
