"""Bluetooth Label ETAG protocol, verified on a 2.13-inch BWR tag."""

from ..base import AdvertisementInfo, Capabilities, EslProtocol
from . import writer
from .devices import PRESETS
from .parser import EtagParser


class EtagProtocol(EslProtocol):
    id = "etag"
    label = "ETAG"
    name = "Bluetooth Label / ETAG (FFE0)"
    capabilities = Capabilities(False, False, False, ("BWR",))
    PRESETS = PRESETS
    parser_cls = EtagParser
    prepare_image = staticmethod(writer.prepare)
    write_session = staticmethod(writer.write_session)

    def parse_advertisement(self, service_info):
        return AdvertisementInfo(model_key="etag213") if self.supported(service_info) else None
