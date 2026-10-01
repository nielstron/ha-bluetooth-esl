"""The BLE ESL integration."""

from __future__ import annotations

from asyncio import Lock
from functools import partial
import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceRegistry,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from sensor_state_data import SensorUpdate

from . import esl_ble
from .const import (
    CONF_MODEL,
    CONF_PROTOCOL,
    DATA_LOCK,
    DEFAULT_MODEL,
    DEFAULT_PROTOCOL,
    DOMAIN,
    WRITE_LOCK,
)
from .coordinator import BleEslPassiveBluetoothProcessorCoordinator
from .data import BleEslRuntimeData
from .designer import KEY as DESIGNER_KEY, async_setup_designer
from .device import format_model_name, resolve_preset
from .services import async_setup_services, cancel_pending_write
from .storage import ImageStore
from .types import BleEslConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.IMAGE,
    Platform.TEXT,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)

# Config-entry only: a `ble_esl:` YAML section is rejected at startup.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up domain-wide state: the BLE write lock and the services."""
    hass.data[DATA_LOCK] = Lock()
    async_setup_services(hass)
    await async_setup_designer(hass)
    return True


def process_service_info(
    hass: HomeAssistant,
    entry: BleEslConfigEntry,
    device_registry: DeviceRegistry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    data = entry.runtime_data
    update = data.parser.update(service_info)

    adv_info = data.protocol.parse_advertisement(service_info)
    if adv_info is None:
        return update

    data.preset = data.protocol.refine_preset(data.preset, adv_info)
    data.parser.set_preset(data.preset)

    # Mirror what the advertisement tells us about the tag onto the device.
    update_kwargs: dict[str, Any] = {}
    if adv_info.sw_version and adv_info.sw_version != data.sw_version:
        data.sw_version = update_kwargs["sw_version"] = adv_info.sw_version
    if adv_info.hw_version and adv_info.hw_version != data.hw_version:
        data.hw_version = update_kwargs["hw_version"] = adv_info.hw_version
    if (model := format_model_name(data.preset)) != data.model:
        data.model = update_kwargs["model"] = model
    if (manufacturer := data.protocol.brand) != data.manufacturer:
        data.manufacturer = update_kwargs["manufacturer"] = manufacturer
    if update_kwargs:
        device_registry.async_update_device(data.device_id, **update_kwargs)

    return update


async def async_setup_entry(hass: HomeAssistant, entry: BleEslConfigEntry) -> bool:
    """Set up a BLE ESL device from a config entry."""
    address = entry.unique_id
    assert address is not None

    options = {**entry.data, **entry.options}
    protocol_id = options.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
    try:
        protocol = esl_ble.get(protocol_id)
    except KeyError as exc:
        # Protocol ids are not migrated: for an entry from a release that used
        # another id, the user removes the device and adds the tag again.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unknown_protocol",
            translation_placeholders={"protocol": protocol_id},
        ) from exc
    preset, service_info, adv_info = resolve_preset(
        hass, protocol, address, options.get(CONF_MODEL, DEFAULT_MODEL)
    )

    parser = protocol.create_parser(preset=preset)
    if service_info:
        parser.update(service_info)

    identifier = address.replace(":", "")[-8:]
    manufacturer = protocol.brand
    model = format_model_name(preset)
    sw_version = adv_info.sw_version if adv_info else None
    hw_version = adv_info.hw_version if adv_info else None

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_BLUETOOTH, address)},
        manufacturer=manufacturer,
        name=f"{manufacturer} {identifier}",
        model=model,
        model_id=protocol.label,
        sw_version=sw_version,
        hw_version=hw_version,
    )

    # The last written / rendered images from the previous run, so the tag
    # is not rewritten with an unchanged image after a restart and the
    # image entities are not blank until the next write.
    image_store = ImageStore(hass, entry.entry_id)
    images = await image_store.async_load()

    bt_coordinator = BleEslPassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=partial(process_service_info, hass, entry, device_registry),
        device_data=parser,
        connectable=True,
    )

    def coordinator(purpose: str, initial: Any) -> DataUpdateCoordinator[Any]:
        """A push-only coordinator seeded with `initial`, named for the log."""
        coord: DataUpdateCoordinator[Any] = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{DOMAIN} {identifier} {purpose}"
        )
        coord.async_set_updated_data(initial)
        return coord

    entry.runtime_data = BleEslRuntimeData(
        address=address,
        protocol=protocol,
        preset=preset,
        parser=parser,
        device_id=device_entry.id,
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        bt_coordinator=bt_coordinator,
        image_coordinator=coordinator("image", images.written.png if images.written else None),
        preview_coordinator=coordinator("preview", images.preview.png if images.preview else None),
        connectivity_coordinator=coordinator("connectivity", False),
        duration_coordinator=coordinator("duration", 0.0),
        failure_coordinator=coordinator("failures", 0),
        last_failure_coordinator=coordinator("last_failure", None),
        battery_coordinator=coordinator("battery", None),
        temperature_coordinator=coordinator("temperature", None),
        image_store=image_store,
        last_image_data=images.written.png if images.written else None,
        # Seeded from the persisted switch state so a write arriving before
        # the switch entity is added is already gated.
        write_lock=bool(entry.data.get(WRITE_LOCK, False)),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(bt_coordinator.async_start())
    hass.data[DESIGNER_KEY].attach(entry)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: BleEslConfigEntry) -> None:
    """Delete the entry's stored images along with the entry."""
    await ImageStore(hass, entry.entry_id).async_remove()
    designer = hass.data[DESIGNER_KEY]
    designer.detach(entry.entry_id)
    designer.documents.pop(entry.entry_id, None)
    await designer.store.async_save(designer.documents)


async def async_unload_entry(hass: HomeAssistant, entry: BleEslConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DESIGNER_KEY].detach(entry.entry_id)
        # Cancels a pending debounce timer and bumps the generation, so a
        # debounced write that already fired but is still queued on the BLE
        # lock is dropped instead of writing to an unloaded entry's tag.
        cancel_pending_write(entry.runtime_data)
        # The images are saved with a delay; a reload must not race it.
        await entry.runtime_data.image_store.async_flush()
    return unload_ok
