"""Minew MTag15 discovery only; authenticated writes are not verified."""

from ..base import AdvertisementInfo, Capabilities, EslProtocol, WriteRefused
from . import writer
from .devices import PRESETS
from .parser import MinewParser
from .wire import device_info


class MinewProtocol(EslProtocol):
    id = "minew"
    label = "Minew"
    name = "Minew MTag15 (discovery only)"
    writable = False
    capabilities = Capabilities(True, False, False, ("BWRY",))
    PRESETS = PRESETS
    parser_cls = MinewParser
    prepare_image = staticmethod(writer.prepare)
    write_session = staticmethod(writer.write_session)

    def parse_advertisement(self, service_info):
        info = device_info(service_info)
        if info is None:
            return None
        return AdvertisementInfo(
            model_key="mtag15" if info["screen_id"] == 65 else None,
            sw_version=info["firmware"],
            raw=info,
        )

    async def write_prepared(self, *args, **kwargs):
        raise WriteRefused("Minew authentication and image writes are not yet verified")
