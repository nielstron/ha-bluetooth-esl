"""Editor persistence, rendering, sensor updates and lifecycle in real HA."""

import base64
from io import BytesIO
from unittest.mock import patch

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.core import HomeAssistant
from PIL import Image
import pytest
import voluptuous as vol

from custom_components.ble_esl.designer import KEY
from custom_components.ble_esl.designer.layout import compile_payload, validate, validate_template
from custom_components.ble_esl.esl_ble.base import DevicePreset


def document():
    return {
        "version": 1,
        "elements": [
            {
                "id": "temperature",
                "type": "sensor",
                "entity_id": "sensor.room_temperature",
                "x": 8,
                "y": 8,
                "width": 180,
                "height": 70,
                "font_size": 32,
                "decimals": 1,
            }
        ],
    }


def test_validation_rejects_unsupported_palette():
    preset = DevicePreset("test", "test", 250, 122, "BWR")
    doc = document()
    doc["background"] = "yellow"
    with pytest.raises(vol.Invalid, match="Background"):
        validate(doc, preset)


async def test_sensor_value_and_unavailable(hass: HomeAssistant):
    doc = validate(document(), DevicePreset("test", "test", 250, 122, "BWR"))
    hass.states.async_set(
        "sensor.room_temperature", "21.26", {"friendly_name": "Office", "unit_of_measurement": "°C"}
    )
    payload = compile_payload(hass, doc)
    assert payload[1]["value"] == "Office"
    assert payload[2]["value"] == "21.3 °C"
    hass.states.async_set("sensor.room_temperature", "unavailable", {"unit_of_measurement": "°C"})
    assert compile_payload(hass, doc)[2]["value"] == "Unavailable"


async def test_panel_preview_save_and_restore(hass: HomeAssistant, wolink_entry):
    assert "ble-esl-designer" in hass.data[DATA_PANELS]
    designer = hass.data[KEY]
    entry = wolink_entry
    hass.states.async_set(
        "sensor.room_temperature", "21.26", {"friendly_name": "Office", "unit_of_measurement": "°C"}
    )
    saved = await designer.save(entry, document())
    assert saved["auto_update"] is False
    result = await designer.preview(entry, saved)
    with Image.open(BytesIO(base64.b64decode(result["png"].split(",")[1]))) as image:
        assert image.size == (296, 128)
        assert image.getextrema() != ((255, 255), (255, 255), (255, 255))
    assert result["payload"][2]["value"] == "21.3 °C"
    assert (await designer.store.async_load())[entry.entry_id] == saved
    await hass.config_entries.async_reload(entry.entry_id)
    assert designer.documents[entry.entry_id] == saved


async def test_send_duplicate_and_lock(hass: HomeAssistant, wolink_entry, tag_writer):
    designer = hass.data[KEY]
    entry = wolink_entry
    assert (await designer.send(entry, document()))["status"] == "written"
    assert (await designer.send(entry, document()))["status"] == "duplicate"
    assert tag_writer.write_prepared.await_count == 1
    entry.runtime_data.write_lock = True
    doc = document()
    doc["elements"][0]["label"] = "Changed label"
    assert (await designer.send(entry, doc))["status"] == "locked"
    assert tag_writer.write_prepared.await_count == 1


async def test_auto_update_coalesces_and_detaches(hass: HomeAssistant, wolink_entry):
    designer = hass.data[KEY]
    entry = wolink_entry
    doc = {**document(), "auto_update": True, "interval": 60}
    with patch("custom_components.ble_esl.designer.async_call_later") as later:
        saved = await designer.save(entry, doc)
        assert saved["auto_update"] is True
        assert later.call_count == 1
        hass.states.async_set("sensor.room_temperature", "25")
        await hass.async_block_till_done()
        assert later.call_count == 1
        assert entry.entry_id in designer.listeners
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.entry_id not in designer.listeners
        assert entry.entry_id not in designer.timers
        later.return_value.assert_called_once()


async def test_websocket_list_preview_validation_and_admin(
    hass: HomeAssistant, wolink_entry, hass_ws_client
):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "ble_esl/designer", "action": "list"})
    result = await client.receive_json()
    assert result["success"]
    assert result["result"][0]["entry_id"] == wolink_entry.entry_id
    await client.send_json(
        {
            "id": 2,
            "type": "ble_esl/designer",
            "action": "preview",
            "entry_id": wolink_entry.entry_id,
            "document": document(),
        }
    )
    result = await client.receive_json()
    assert result["success"]
    assert result["result"]["png"].startswith("data:image/png;base64,")
    await client.send_json(
        {
            "id": 3,
            "type": "ble_esl/designer",
            "action": "save",
            "entry_id": wolink_entry.entry_id,
            "document": {"version": 99, "elements": []},
        }
    )
    assert (await client.receive_json())["success"] is False


async def test_temperature_compatibility_unit(hass: HomeAssistant):
    """A reported superscript-zero temperature unit must not become a missing glyph."""
    doc = validate(document(), DevicePreset("test", "test", 250, 122, "BWR"))
    hass.states.async_set("sensor.room_temperature", "21.26", {"unit_of_measurement": "⁰C"})
    assert compile_payload(hass, doc)[2]["value"] == "21.3 °C"


async def test_template_persistence_state_icons_and_scaled_rendering(hass, wolink_entry):
    from custom_components.ble_esl.designer.layout import validate_template

    designer = hass.data[KEY]
    template = {
        "width": 100,
        "height": 50,
        "document": {
            "version": 1,
            "elements": [
                {
                    "id": "on",
                    "type": "icon",
                    "icon": "mdi:window-open",
                    "state": "on",
                    "x": 0,
                    "y": 0,
                    "width": 30,
                    "height": 30,
                },
                {
                    "id": "off",
                    "type": "icon",
                    "icon": "mdi:window-closed",
                    "state": "off",
                    "x": 0,
                    "y": 0,
                    "width": 30,
                    "height": 30,
                },
                {
                    "id": "name",
                    "type": "text",
                    "text": "{{name}}",
                    "x": 35,
                    "y": 0,
                    "width": 65,
                    "height": 20,
                },
            ],
        },
    }
    await designer.save_template("binary_sensor:window", template)
    assert (await designer.template_store.async_load())[
        "binary_sensor:window"
    ] == validate_template(template)
    doc = document()
    doc["elements"][0].update(entity_id="binary_sensor.window", width=200, height=100)
    del doc["elements"][0]["decimals"]
    doc = validate(doc, DevicePreset("test", "test", 250, 122, "BWR"))
    hass.states.async_set(
        "binary_sensor.window", "off", {"device_class": "window", "friendly_name": "Window"}
    )
    payload = compile_payload(hass, doc, designer.templates)
    assert payload[0]["value"] == "mdi:window-closed"
    assert payload[0]["size"] == 60
    assert payload[1]["x"] == 78
    assert payload[1]["value"] == "Window"
    hass.states.async_set(
        "binary_sensor.window", "on", {"device_class": "window", "friendly_name": "Window"}
    )
    assert compile_payload(hass, doc, designer.templates)[0]["value"] == "mdi:window-open"
    preview = await designer.preview_template(template, "binary_sensor.window")
    with Image.open(BytesIO(base64.b64decode(preview["png"].split(",")[1]))) as image:
        assert image.size == (100, 50)


async def test_weather_forecast_and_visual_condition(hass):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    hass.states.async_set(
        "weather.home",
        "cloudy",
        {"friendly_name": "Weather", "temperature": 18, "temperature_unit": "°C"},
    )
    doc = document()
    doc["elements"][0].update(
        entity_id="weather.home", weather_when="tomorrow", weather_field="condition"
    )
    del doc["elements"][0]["decimals"]
    doc = validate(doc, DevicePreset("test", "test", 250, 122, "BWR"))
    forecasts = {
        ("weather.home", "daily"): [
            {
                "datetime": (dt_util.now() + timedelta(days=1)).isoformat(),
                "condition": "sunny",
                "temperature": 23.5,
            }
        ]
    }
    payload = compile_payload(hass, doc, forecasts=forecasts)
    assert payload[0]["value"] == "mdi:weather-sunny"
    assert all(item.get("value") not in ("cloudy", "sunny") for item in payload)
    doc["elements"][0]["weather_field"] = "temperature"
    payload = compile_payload(hass, doc, forecasts=forecasts)
    assert payload[0]["value"] == "mdi:thermometer"
    assert payload[2]["value"] == "23.5 °C"


async def test_default_entity_icon_and_binary_state(hass):
    from custom_components.ble_esl.designer.layout import sensor_icon

    hass.states.async_set("binary_sensor.window", "off", {"device_class": "window"})
    assert sensor_icon(hass.states.get("binary_sensor.window")) == "mdi:window-closed"
    hass.states.async_set("binary_sensor.window", "on", {"device_class": "window"})
    assert sensor_icon(hass.states.get("binary_sensor.window")) == "mdi:window-open"
    hass.states.async_set(
        "sensor.temperature", "21", {"device_class": "temperature", "icon": "mdi:home-thermometer"}
    )
    assert sensor_icon(hass.states.get("sensor.temperature")) == "mdi:home-thermometer"


async def test_weather_forecasts_use_ha_service_and_cache(hass, wolink_entry):
    from homeassistant.core import SupportsResponse

    designer = hass.data[KEY]
    doc = validate(document(), wolink_entry.runtime_data.preset)
    doc["elements"][0].update(entity_id="weather.home", weather_when="tomorrow")
    forecast = [{"datetime": "2026-10-02T12:00:00+00:00", "condition": "cloudy"}]
    calls = []

    async def get_forecasts(call):
        calls.append(dict(call.data))
        return {"weather.home": {"forecast": forecast}}

    hass.services.async_register(
        "weather", "get_forecasts", get_forecasts, supports_response=SupportsResponse.ONLY
    )
    assert await designer.forecasts(doc) == {("weather.home", "daily"): forecast}
    assert await designer.forecasts(doc) == {("weather.home", "daily"): forecast}
    assert calls == [{"entity_id": "weather.home", "type": "daily"}]


def test_elements_can_extend_outside_display():
    doc = document()
    doc["elements"][0].update(x=-20, y=-10, width=300, height=160)
    result = validate(doc, DevicePreset("test", "test", 250, 122, "BWR"))
    assert result["elements"][0]["x"] == -20
    assert result["elements"][0]["width"] == 300


async def test_sensor_background_can_be_transparent(hass):
    doc = document()
    doc["elements"][0]["background"] = "transparent"
    validated = validate(doc, DevicePreset("test", "test", 250, 122, "BWR"))
    hass.states.async_set("sensor.room_temperature", "21.2", {"unit_of_measurement": "°C"})
    assert "background" not in compile_payload(hass, validated)[2]


async def test_explicit_text_line_breaks_are_preserved(hass, wolink_entry):
    doc = {
        "version": 1,
        "elements": [
            {
                "id": "text",
                "type": "text",
                "text": "A\nB",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 80,
                "font_size": 18,
            }
        ],
    }
    result = await hass.data[KEY].preview(wolink_entry, doc)
    with Image.open(BytesIO(base64.b64decode(result["png"].split(",")[1]))) as image:
        assert image.crop((0, 0, 100, 40)).getextrema() != ((255, 255), (255, 255), (255, 255))
        assert image.crop((0, 40, 100, 80)).getextrema() != ((255, 255), (255, 255), (255, 255))


async def test_preview_composes_exact_layers_and_crops(hass, wolink_entry):
    doc = {
        "version": 1,
        "elements": [
            {
                "id": "base",
                "type": "rectangle",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 80,
                "color": "red",
            },
            {
                "id": "overlay",
                "type": "text",
                "text": "A",
                "x": -4,
                "y": 3,
                "width": 100,
                "height": 60,
                "font_size": 18,
            },
        ],
    }
    result = await hass.data[KEY].preview(wolink_entry, doc)

    def decode(value):
        return Image.open(BytesIO(base64.b64decode(value.split(",")[1])))

    with decode(result["png"]) as actual:
        expected = Image.new("RGB", actual.size, "white")
        for element in doc["elements"]:
            with decode(result["layers"][element["id"]]) as layer:
                expected.paste(layer, (element["x"], element["y"]), layer)
        assert actual.tobytes() == expected.tobytes()
        assert actual.getpixel((90, 70)) == (255, 0, 0)
        with decode(result["layers"]["overlay"]) as layer:
            assert layer.getpixel((99, 59))[3] == 0


async def test_numeric_template_applies_across_sensor_device_classes(hass):
    hass.states.async_set("sensor.room_temperature", "21.2", {"device_class": "temperature"})
    doc = validate(document(), DevicePreset("test", "test", 250, 122, "BWR"))
    template = validate_template(
        {
            "width": 100,
            "height": 60,
            "sensor_type": "output:numeric",
            "document": {
                "version": 1,
                "elements": [
                    {
                        "id": "value",
                        "type": "text",
                        "text": "Shared {{state}}",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 60,
                    }
                ],
            },
        }
    )
    payload = compile_payload(hass, doc, {"output:numeric": template})
    assert any(item.get("value") == "Shared 21.2" for item in payload)


async def test_image_elements_and_state_images_render(hass, wolink_entry):
    from custom_components.ble_esl.designer.rendering import png_url

    source = png_url(Image.new("RGB", (4, 4), "red"))
    doc = {
        "version": 1,
        "elements": [
            {
                "id": "picture",
                "type": "image",
                "image": source,
                "x": 4,
                "y": 5,
                "width": 20,
                "height": 20,
            }
        ],
    }
    result = await hass.data[KEY].preview(wolink_entry, doc)
    with Image.open(BytesIO(base64.b64decode(result["png"].split(",")[1]))) as image:
        assert image.getpixel((10, 10)) == (255, 0, 0)
    hass.states.async_set("binary_sensor.laundry", "on")
    template = validate_template(
        {
            "width": 30,
            "height": 30,
            "document": {
                "version": 1,
                "elements": [
                    dict(doc["elements"][0], state="on"),
                    dict(doc["elements"][0], id="off", state="off"),
                ],
            },
        }
    )
    sensor = validate(
        {
            "version": 1,
            "elements": [
                {
                    "id": "laundry",
                    "type": "sensor",
                    "entity_id": "binary_sensor.laundry",
                    "template": "output:binary",
                    "x": 0,
                    "y": 0,
                    "width": 30,
                    "height": 30,
                }
            ],
        },
        DevicePreset("test", "test", 250, 122, "BWR"),
    )
    assert len(compile_payload(hass, sensor, {"output:binary": template})) == 1


async def test_state_icon_mapping_selects_the_current_sensor_state(hass):
    from custom_components.ble_esl.designer.layout import substitute

    template = validate_template(
        {
            "width": 50,
            "height": 50,
            "document": {
                "version": 1,
                "elements": [
                    {
                        "id": "icon",
                        "type": "icon",
                        "x": 0,
                        "y": 0,
                        "width": 32,
                        "height": 32,
                        "icon": "{{icon}}",
                        "state_icons": {
                            "on": "mdi:washing-machine",
                            "off": "mdi:washing-machine-off",
                        },
                    }
                ],
            },
        }
    )
    for state, expected in [
        ("on", "mdi:washing-machine"),
        ("off", "mdi:washing-machine-off"),
        ("unavailable", "mdi:help"),
    ]:
        resolved = substitute(template["document"], {"icon": "mdi:help"}, state)
        assert compile_payload(hass, resolved)[0]["value"] == expected
