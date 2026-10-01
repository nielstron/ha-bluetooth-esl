"""Explicit registry: add a driver instance here to expose it to the CLI."""

from .etag213 import Etag213Driver
from .minew154 import Minew154Driver

DRIVERS = {driver.name: driver for driver in (Etag213Driver(), Minew154Driver())}
DEFAULT_DRIVER = "etag213"


def get_driver(name):
    return DRIVERS[name]
