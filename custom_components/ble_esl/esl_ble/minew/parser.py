from sensor_state_data import SensorLibrary

from ..base import BleParser
from .const import BRAND, COMPANY_ID
from .wire import device_info


def is_minew_advertisement(info):
    return info.manufacturer_data.get(COMPANY_ID, b"")[:1] == b"\xca"


class MinewParser(BleParser):
    brand = BRAND
    fallback_name = "MTag15 (discovery only)"
    is_advertisement = staticmethod(is_minew_advertisement)

    def _parse(self, service_info):
        info = device_info(service_info)
        if info is not None:
            self.update_predefined_sensor(
                SensorLibrary.BATTERY__PERCENTAGE, info["battery_percent"]
            )
