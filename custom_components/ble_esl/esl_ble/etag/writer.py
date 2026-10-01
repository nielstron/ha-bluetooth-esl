from ..._vendor.ble_labels.tags.etag213 import EtagConnection
from ..base import WriteResult
from .const import FIRMWARE
from .image import encode_image


def prepare(preset, image, address):
    return encode_image(image, preset)


async def write_session(client, address, preset, prepared, *, pacing_s=0.0, trace):
    firmware = (await client.read_gatt_char(FIRMWARE)).decode()
    if not any(panel in firmware for panel in ("SE0213NP61-TNG-A0", "SE0213MN50-TNG-A0")):
        raise ValueError(f"Unsupported ETAG panel firmware: {firmware}")
    image = await prepared
    with trace.timed("transfer"):
        await EtagConnection(client, firmware).write(
            image, timeout=30, log=[], progress=lambda done, total: None
        )
    return WriteResult(success=True)
