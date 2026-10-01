from ..base import BleParser
from .const import BRAND


def is_etag_advertisement(info):
    return isinstance(info.name, str) and info.name.startswith("ETAG-")


class EtagParser(BleParser):
    brand = BRAND
    fallback_name = "ETAG 2.13"
    is_advertisement = staticmethod(is_etag_advertisement)
