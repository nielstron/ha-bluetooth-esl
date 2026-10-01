"""Config and options flows through Home Assistant's flow manager."""

from __future__ import annotations

from unittest.mock import patch

from bt import inject_bluetooth_service_info, service_info
from conftest import ADDRESS, IDENT, setup_entry, wolink_service_info
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
import voluptuous as vol

from custom_components.ble_esl.config_flow import _model_selector_options
from custom_components.ble_esl.const import (
    CONF_DEBOUNCE_MS,
    CONF_MODEL,
    CONF_PREVENT_DUPLICATE_SEND,
    CONF_PROTOCOL,
    CONF_RETRY_COUNT,
    DOMAIN,
)
from custom_components.ble_esl.esl_ble.easytag.const import SERVICE_UUID as EASYTAG_UUID
from custom_components.ble_esl.esl_ble.picksmart.const import MANUFACTURER_ID as PICKSMART_ID
from custom_components.ble_esl.esl_ble.wolink.devices import PRESETS


@pytest.fixture(autouse=True)
def onboarded_home_assistant():
    """These discovery tests represent an installed, already onboarded HA."""
    with patch("homeassistant.components.onboarding.async_is_onboarded", return_value=True):
        yield


PICKSMART_ADDRESS = "AA:BB:CC:DD:EE:33"
POSHIJI_ADDRESS = "AA:BB:CC:DD:EE:42"


def picksmart_service_info():
    # device 0x0033 (2.9" EPD BWR), firmware 0x8101, 2.6 V
    return service_info(
        PICKSMART_ADDRESS,
        name="PickSmart",
        manufacturer_data={PICKSMART_ID: bytes([0x33, 0x1A, 0x81, 0x01, 0x40])},
    )


def xte_service_info():
    return service_info(
        POSHIJI_ADDRESS,
        name="FFEEDDCCBBAA",
        manufacturer_data={0x5258: bytes.fromhex("fd024002009964060102ffff1b")},
    )


async def start_bluetooth_flow(hass: HomeAssistant, info):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=info
    )


# ── Discovery ────────────────────────────────────────────────────────────


async def test_bluetooth_discovery_wolink_known_display_skips_model(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """A captured display version registers the preset without a model step."""
    info = wolink_service_info(mfr_bytes=bytes.fromhex("3000000e033003030b9d"))
    result = await start_bluetooth_flow(hass, info)
    assert result["step_id"] == "bluetooth_confirm"
    assert '2.9" BWR' in result["description_placeholders"]["name"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PROTOCOL: "wolink", CONF_MODEL: "290-bwr"}
    assert result["result"].runtime_data.preset.key == "290-bwr"


async def test_bluetooth_discovery_wolink_asks_for_model(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    result = await start_bluetooth_flow(hass, wolink_service_info())
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"]["name"] == f"Zhsunyco {IDENT} (WOLINK (BWRY))"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODEL: "350"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f'Zhsunyco {IDENT} (3.5" BWRY)'
    assert result["data"] == {CONF_PROTOCOL: "wolink", CONF_MODEL: "350"}
    entry = result["result"]
    assert entry.unique_id == ADDRESS
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.preset.key == "350"


async def test_bluetooth_discovery_picksmart_detects_model(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """A protocol with model detection skips the model step."""
    result = await start_bluetooth_flow(hass, picksmart_service_info())
    assert result["step_id"] == "bluetooth_confirm"
    assert '2.9" EPD BWR' in result["description_placeholders"]["name"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PROTOCOL: "picksmart", CONF_MODEL: "0x0033"}


async def test_bluetooth_discovery_xte(hass: HomeAssistant, enable_bluetooth) -> None:
    result = await start_bluetooth_flow(hass, xte_service_info())
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PROTOCOL: "xte", CONF_MODEL: "psj-420"}


async def test_bluetooth_discovery_xte_unknown_device_number_asks_for_model(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """An uncaptured device number falls back to the model picker with the size-only presets."""
    info = service_info(
        POSHIJI_ADDRESS,
        name="FFEEDDCCBBAA",
        manufacturer_data={0x5258: bytes.fromhex("fd024002008d63060102ffff1b")},
    )
    result = await start_bluetooth_flow(hass, info)
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    # No size is a better guess than another: the picker has no default.
    field = next(k for k in result["data_schema"].schema if k == CONF_MODEL)
    assert field.default is vol.UNDEFINED
    labels = {o["value"]: o["label"] for o in _model_selector_options("xte")}
    assert labels["psj-290"] == '2.9" BWRY — 296x128'
    assert labels["psj-420"] == 'PSJ-420 4.2" BWRY — 400x300'

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODEL: "psj-290"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PROTOCOL: "xte", CONF_MODEL: "psj-290"}
    assert result["result"].runtime_data.preset.key == "psj-290"
    assert result["title"].startswith("Poshiji ")


async def test_bluetooth_discovery_unsupported_and_already_configured(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    result = await start_bluetooth_flow(hass, service_info("00:11:22:33:44:55", name="Other"))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"

    # (advertise=False: injecting the advertisement would itself start a
    # discovery flow, and a second one would abort as already_in_progress.)
    await setup_entry(hass, advertise=False)
    result = await start_bluetooth_flow(hass, wolink_service_info())
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_lists_discovered_tags(hass: HomeAssistant, enable_bluetooth) -> None:
    inject_bluetooth_service_info(hass, wolink_service_info())
    inject_bluetooth_service_info(hass, picksmart_service_info())

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
    )
    assert result["step_id"] == "model"  # WOLINK needs a model
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MODEL: "290"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ADDRESS


async def test_user_flow_without_devices_aborts(hass: HomeAssistant, enable_bluetooth) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# ── Options ──────────────────────────────────────────────────────────────


async def test_options_flow_updates_and_reloads(hass: HomeAssistant, enable_bluetooth) -> None:
    # An entry saved by a release that still had the Write Delay option loads
    # fine; the stale key is neither shown nor kept once options are saved.
    # easyTag still offers a model; WOLINK reads it from the advertisement.
    inject_bluetooth_service_info(
        hass, service_info(ADDRESS, name="easyTag", service_uuids=[EASYTAG_UUID])
    )
    entry = await setup_entry(
        hass, protocol="easytag", model="33", options={"write_delay_ms": 50}, advertise=False
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    fields = {str(key) for key in result["data_schema"].schema}
    assert "write_delay_ms" not in fields
    assert {
        CONF_MODEL,
        CONF_RETRY_COUNT,
        CONF_PREVENT_DUPLICATE_SEND,
        CONF_DEBOUNCE_MS,
    } <= fields

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "36",
            CONF_RETRY_COUNT: 5,
            CONF_PREVENT_DUPLICATE_SEND: True,
            CONF_DEBOUNCE_MS: 2000,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_MODEL: "36",
        CONF_RETRY_COUNT: 5,
        CONF_PREVENT_DUPLICATE_SEND: True,
        CONF_DEBOUNCE_MS: 2000,
    }
    # OptionsFlowWithReload reloaded the entry: the new model is in force.
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.preset.key == "36"


async def test_options_flow_hides_identified_wolink_model(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """A known display version fixes the model, so options do not offer one."""
    inject_bluetooth_service_info(
        hass, wolink_service_info(mfr_bytes=bytes.fromhex("3000000e033002010b8b"))
    )
    entry = await setup_entry(hass, model="290", advertise=False)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key) for key in result["data_schema"].schema}
    assert CONF_MODEL not in fields
    assert CONF_RETRY_COUNT in fields
    assert entry.runtime_data.preset.key == "350"


async def test_options_flow_offers_model_for_unidentified_wolink(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """An unknown display version leaves the model to the user, in options too."""
    entry = await setup_entry(hass, model="290")  # fixture display version 0x0605
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key) for key in result["data_schema"].schema}
    assert CONF_MODEL in fields

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MODEL: "290-bwr",
            CONF_RETRY_COUNT: 3,
            CONF_PREVENT_DUPLICATE_SEND: False,
            CONF_DEBOUNCE_MS: 0,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.runtime_data.preset.key == "290-bwr"


async def test_options_flow_keeps_model_when_hidden(hass: HomeAssistant, enable_bluetooth) -> None:
    """Saving options with the model hidden keeps a model picked earlier."""
    inject_bluetooth_service_info(
        hass, wolink_service_info(mfr_bytes=bytes.fromhex("3000000e033002010b8b"))
    )
    entry = await setup_entry(hass, model="290", options={CONF_MODEL: "350"}, advertise=False)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert CONF_MODEL not in {str(key) for key in result["data_schema"].schema}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RETRY_COUNT: 5,
            CONF_PREVENT_DUPLICATE_SEND: False,
            CONF_DEBOUNCE_MS: 0,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MODEL] == "350"
    assert entry.options[CONF_RETRY_COUNT] == 5


async def test_options_flow_hides_model_when_the_tag_is_silent(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    """A missing advertisement is not an unidentified model."""
    entry = await setup_entry(
        hass, address=PICKSMART_ADDRESS, protocol="picksmart", model="0x0033", advertise=False
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key) for key in result["data_schema"].schema}
    assert CONF_MODEL not in fields


async def test_options_flow_hides_model_for_model_detection_protocol(
    hass: HomeAssistant, enable_bluetooth
) -> None:
    inject_bluetooth_service_info(hass, picksmart_service_info())
    entry = await setup_entry(
        hass, address=PICKSMART_ADDRESS, protocol="picksmart", model="0x0033", advertise=False
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key) for key in result["data_schema"].schema}
    assert CONF_MODEL not in fields
    assert CONF_RETRY_COUNT in fields


# ── Model list ───────────────────────────────────────────────────────────


def test_model_selector_options_sorted_by_size():
    options = _model_selector_options("wolink")
    assert len(options) == len(PRESETS)
    keys = [o["value"] for o in options]
    expected_order = sorted(PRESETS.keys(), key=lambda k: PRESETS[k].width * PRESETS[k].height)
    assert keys == expected_order
    for option in options:
        preset = PRESETS[option["value"]]
        assert option["label"] == f"{preset.display_name} — {preset.width}x{preset.height}"


def test_options_schema_default_model_falls_back_per_protocol():
    """DEFAULT_MODEL ("290") is WOLINK's; other protocols default to their first preset."""
    from custom_components.ble_esl.config_flow import _build_options_schema
    from custom_components.ble_esl.esl_ble.easytag.devices import PRESETS as EASYTAG_PRESETS

    def model_default(protocol):
        for key in _build_options_schema(protocol):
            if str(key) == CONF_MODEL:
                return key.default()
        raise AssertionError("no model field")

    assert model_default("wolink") == "290"
    assert model_default("easytag") == next(iter(EASYTAG_PRESETS))
    identified = _build_options_schema("wolink", model_fixed=True)
    assert all(str(key) != CONF_MODEL for key in identified)
