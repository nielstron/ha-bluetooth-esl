"""Versioned editor documents compiled into ordinary imagespec payloads."""

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

from homeassistant.util import dt as dt_util
import voluptuous as vol

COLOR = vol.In(("black", "white", "red", "yellow"))
ELEMENT = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("type"): vol.In(
            (
                "sensor",
                "image",
                "text",
                "rectangle",
                "line",
                "icon",
                "ellipse",
                "triangle",
                "rounded_rectangle",
            )
        ),
        vol.Required("x"): int,
        vol.Required("y"): int,
        vol.Required("width"): vol.All(int, vol.Range(min=1)),
        vol.Required("height"): vol.All(int, vol.Range(min=1)),
        vol.Optional("color", default="black"): COLOR,
        vol.Optional("background", default="transparent"): vol.In(
            ("black", "white", "red", "yellow", "transparent")
        ),
        vol.Optional("font_size", default=24): vol.All(int, vol.Range(min=8, max=200)),
        vol.Optional("text", default="Text"): str,
        vol.Optional("image", default=""): str,
        vol.Optional("image_fit", default="contain"): vol.In(("contain", "fill", "stretch")),
        vol.Optional("icon", default="{{icon}}"): str,
        vol.Optional("state", default=""): str,
        vol.Optional("state_icons", default=dict): {str: str},
        vol.Optional("template", default="auto"): str,
        vol.Optional("weather_when", default="now"): vol.In(
            ("now", "later_today", "tomorrow", "in_2_days", "in_3_days")
        ),
        vol.Optional("weather_field", default="condition"): vol.In(
            (
                "condition",
                "temperature",
                "templow",
                "precipitation",
                "precipitation_probability",
                "wind_speed",
                "humidity",
            )
        ),
        vol.Optional("entity_id", default=""): str,
        vol.Optional("label", default=""): str,
        vol.Optional("show_label", default=True): bool,
        vol.Optional("show_unit", default=True): bool,
        vol.Optional("decimals"): vol.All(int, vol.Range(min=0, max=6)),
        vol.Optional("align", default="left"): vol.In(("left", "center", "right")),
    }
)
DOCUMENT = vol.Schema(
    {
        vol.Required("version"): 1,
        vol.Required("elements"): vol.All([ELEMENT], vol.Length(max=100)),
        vol.Optional("background", default="white"): COLOR,
        vol.Optional("auto_update", default=False): bool,
        vol.Optional("interval", default=60): vol.All(int, vol.Range(min=10, max=86400)),
    }
)


def validate(document, preset):
    """Reject invalid documents before replacing a saved layout."""
    result = DOCUMENT(deepcopy(document))
    palette = (
        {"black", "white"}
        | ({"red"} if "R" in preset.colors else set())
        | ({"yellow"} if "Y" in preset.colors else set())
    )
    if result["background"] not in palette:
        raise vol.Invalid("Background is not supported by this tag")
    ids = set()
    for element in result["elements"]:
        if element["id"] in ids:
            raise vol.Invalid("Element IDs must be unique")
        ids.add(element["id"])
        if element["color"] not in palette or element["background"] not in palette | {
            "transparent"
        }:
            raise vol.Invalid("Element colour is not supported by this tag")
        if element["type"] == "sensor" and not element["entity_id"]:
            raise vol.Invalid("Sensor elements need an entity_id")
    return result


def bindings(document):
    return {element["entity_id"] for element in document["elements"] if element["type"] == "sensor"}


def template_key(state):
    return state.entity_id.split(".")[0] + ":" + state.attributes.get("device_class", "default")


def output_type(state):
    """Template compatibility follows the value, independently of device class."""
    if state.entity_id.startswith("weather."):
        return "weather"
    if state.entity_id.startswith("binary_sensor.") or state.state in ("on", "off"):
        return "binary"
    if state.attributes.get("unit_of_measurement"):
        return "numeric"
    try:
        float(state.state)
    except ValueError:
        return "text"
    return "numeric"


def sensor_icon(state):
    """Respect an entity's HA icon and otherwise use HA device-class icons."""
    if icon := state.attributes.get("icon"):
        return icon
    if state.entity_id.startswith("weather."):
        return "mdi:" + {
            "clear-night": "weather-night",
            "cloudy": "weather-cloudy",
            "fog": "weather-fog",
            "hail": "weather-hail",
            "lightning": "weather-lightning",
            "lightning-rainy": "weather-lightning-rainy",
            "partlycloudy": "weather-partly-cloudy",
            "pouring": "weather-pouring",
            "rainy": "weather-rainy",
            "snowy": "weather-snowy",
            "snowy-rainy": "weather-snowy-rainy",
            "sunny": "weather-sunny",
            "windy": "weather-windy",
            "windy-variant": "weather-windy-variant",
            "exceptional": "alert-circle",
        }.get(state.state, "weather-cloudy")
    device_class = state.attributes.get("device_class", "")
    active = state.state == "on"
    if state.entity_id.startswith("binary_sensor."):
        pairs = {
            "window": ("window-open", "window-closed"),
            "door": ("door-open", "door-closed"),
            "opening": ("square-outline", "square"),
            "motion": ("motion-sensor", "motion-sensor-off"),
            "occupancy": ("home", "home-outline"),
            "presence": ("home", "home-outline"),
            "plug": ("power-plug", "power-plug-off"),
            "power": ("flash", "flash-off"),
            "battery": ("battery-outline", "battery"),
            "connectivity": ("check-network", "close-network"),
            "lock": ("lock-open", "lock"),
            "light": ("brightness-7", "brightness-5"),
        }
        return (
            "mdi:"
            + pairs.get(device_class, ("checkbox-marked-circle", "radiobox-blank"))[not active]
        )
    return "mdi:" + {
        "temperature": "thermometer",
        "humidity": "water-percent",
        "battery": "battery",
        "power": "flash",
        "energy": "lightning-bolt",
        "illuminance": "brightness-5",
        "pressure": "gauge",
        "voltage": "sine-wave",
        "current": "current-ac",
        "signal_strength": "wifi",
        "timestamp": "calendar-clock",
        "wind_speed": "weather-windy",
        "precipitation": "weather-rainy",
    }.get(device_class, "eye")


def normalize_unit(unit):
    # Some integrations report superscript zero, not the degree sign.
    return {"⁰C": "°C", "⁰F": "°F", "℃": "°C", "℉": "°F"}.get(unit, unit)


def weather_state(state, element, forecasts):
    if not state.entity_id.startswith("weather."):
        return state
    field = element.get("weather_field", "condition")
    when = element.get("weather_when", "now")
    values = state.attributes if when == "now" else {}
    condition = state.state
    if when != "now":
        forecast_type = "hourly" if when == "later_today" else "daily"
        days = {"later_today": 0, "tomorrow": 1, "in_2_days": 2, "in_3_days": 3}[when]
        now = dt_util.now()
        date = (now + timedelta(days=days)).date()
        for item in forecasts.get((state.entity_id, forecast_type), []):
            stamp = dt_util.parse_datetime(item["datetime"])
            local = dt_util.as_local(stamp)
            if local.date() == date and (when != "later_today" or local > now):
                values = item
                break
        condition = values.get("condition", "unavailable")
    value = condition if field == "condition" else str(values.get(field, "unavailable"))
    attrs = dict(state.attributes)
    if field != "condition":
        attrs.pop("icon", None)
        attrs["device_class"] = {
            "templow": "temperature",
            "precipitation": "precipitation",
            "precipitation_probability": "humidity",
            "wind_speed": "wind_speed",
        }.get(field, field)
        attrs["unit_of_measurement"] = (
            "%"
            if field in ("humidity", "precipitation_probability")
            else state.attributes.get({"templow": "temperature"}.get(field, field) + "_unit", "")
        )
    # Keep weather condition icons, use sensor device-class icons for numerical weather values.
    return SimpleNamespace(
        entity_id=state.entity_id
        if field == "condition"
        else "sensor." + state.entity_id.split(".")[1],
        state=value,
        attributes=attrs,
    )


def sensor_values(state, element):
    label = element.get("label") or state.attributes.get("friendly_name", state.entity_id)
    value = state.state
    if value in ("unavailable", "unknown"):
        value = value.capitalize()
    elif "decimals" in element:
        value = f"{float(value):.{element['decimals']}f}"
    unit = (
        normalize_unit(state.attributes.get("unit_of_measurement", ""))
        if element.get("show_unit", True)
        else ""
    )
    if state.state in ("unknown", "unavailable"):
        unit = ""
    return {"name": label, "state": value, "unit": unit, "icon": sensor_icon(state)}


def validate_template(template):
    """A sensor template has its own coordinate system, independent of a tag."""
    from ..esl_ble.base import DevicePreset

    schema = vol.Schema(
        {
            vol.Required("width"): vol.All(int, vol.Range(min=16, max=1000)),
            vol.Required("height"): vol.All(int, vol.Range(min=16, max=1000)),
            vol.Required("document"): dict,
            vol.Optional("name", default=""): str,
            vol.Optional("sensor_type", default=""): str,
        }
    )
    result = schema(deepcopy(template))
    result["document"] = validate(
        result["document"],
        DevicePreset("template", "Template", result["width"], result["height"], "BWRY"),
    )
    if any(el["type"] == "sensor" for el in result["document"]["elements"]):
        raise vol.Invalid(
            "Templates contain text, icons and shapes; use {{state}} for the sensor value"
        )
    return result


def substitute(document, values, raw_state):
    result = deepcopy(document)
    result["elements"] = [
        el for el in result["elements"] if not el.get("state") or el["state"] == raw_state
    ]
    for el in result["elements"]:
        if el["type"] == "icon" and raw_state in el.get("state_icons", {}):
            el["icon"] = el["state_icons"][raw_state]
        for field in ("text", "icon"):
            for name, value in values.items():
                el[field] = el.get(field, "").replace("{{" + name + "}}", value)
    return result


def compile_payload(hass, document, templates=None, forecasts=None):
    """Snapshot HA values on its event loop; render them later in the executor."""
    payload = []
    for element in document["elements"]:
        x, y, width, height = (element[key] for key in ("x", "y", "width", "height"))
        color = element["color"]
        state = hass.states.get(element["entity_id"]) if element["type"] == "sensor" else None
        if state is not None:
            state = weather_state(state, element, forecasts or {})
        if element["type"] == "sensor" and templates:
            key = element.get("template", "auto")
            if key == "auto" and state is not None:
                key = template_key(state)
                if key not in templates:
                    key = state.entity_id.split(".")[0] + ":default"
                if key not in templates:
                    key = "output:" + output_type(state)
            if key in templates and state is not None:
                template = templates[key]
                nested = substitute(
                    template["document"], sensor_values(state, element), state.state
                )
                sx, sy = width / template["width"], height / template["height"]
                for child in nested["elements"]:
                    child["x"] = x + round(child["x"] * sx)
                    child["y"] = y + round(child["y"] * sy)
                    child["width"] = max(1, round(child["width"] * sx))
                    child["height"] = max(1, round(child["height"] * sy))
                    child["font_size"] = max(8, round(child["font_size"] * min(sx, sy)))
                payload.extend(compile_payload(hass, nested))
                continue
        if element["type"] == "image":
            if element["image"]:
                payload.append(
                    {
                        "type": "dlimg",
                        "x": x,
                        "y": y,
                        "xsize": width,
                        "ysize": height,
                        "url": element["image"],
                        "mode": element["image_fit"],
                        "dither": True,
                    }
                )
            continue
        if element["type"] == "icon":
            payload.append(
                {
                    "type": "icon",
                    "x": x,
                    "y": y,
                    "size": min(width, height),
                    "value": element["icon"],
                    "color": color,
                    "anchor": "lt",
                }
            )
            continue
        if element["type"] in ("rectangle", "line", "ellipse", "triangle", "rounded_rectangle"):
            if element["type"] == "triangle":
                payload.append(
                    {
                        "type": "polygon",
                        "points": f"{x + width // 2},{y};{x + width - 1},{y + height - 1};{x},{y + height - 1}",
                        "fill": color,
                        "outline": color,
                    }
                )
            else:
                payload.append(
                    {
                        "type": "ellipse" if element["type"] == "ellipse" else "rectangle",
                        "x_start": x,
                        "y_start": y,
                        "x_end": x + width - 1,
                        "y_end": y + height - 1,
                        "fill": color,
                        "outline": color,
                        **(
                            {"radius": max(1, min(width, height) // 5)}
                            if element["type"] == "rounded_rectangle"
                            else {}
                        ),
                    }
                )
            continue
        value = element["text"]
        label = element["label"]
        if element["type"] == "sensor":
            if state is None:
                value = "Unavailable"
                label = label or element["entity_id"]
            else:
                label = label or state.attributes.get("friendly_name", state.entity_id)
                value = state.state
                if value in ("unavailable", "unknown"):
                    value = value.capitalize()
                elif "decimals" in element:
                    value = f"{float(value):.{element['decimals']}f}"
                if element["show_unit"] and state.state not in ("unavailable", "unknown"):
                    unit = normalize_unit(state.attributes.get("unit_of_measurement", ""))
                    value += f" {unit}" if unit else ""
            if state is not None:
                icon_size = min(32, height, max(8, width // 4))
                payload.append(
                    {
                        "type": "icon",
                        "x": x + 4,
                        "y": y + max(0, (height - icon_size) // 2),
                        "size": icon_size,
                        "value": sensor_icon(state),
                        "color": color,
                        "anchor": "lt",
                    }
                )
                x += icon_size + 12
                width = max(1, width - icon_size - 12)
            if state is not None and state.entity_id.startswith(("weather.", "binary_sensor.")):
                if element["show_label"]:
                    payload.append(
                        {
                            "type": "text_fit",
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                            "value": label,
                            "size": 12,
                            "min_size": 8,
                            "fit": "shrink_ellipsis",
                            "color": color,
                            "align": element["align"],
                        }
                    )
                continue
            if element["show_label"]:
                label_height = min(18, max(8, height // 3))
                payload.append(
                    {
                        "type": "text_fit",
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": label_height,
                        "value": label,
                        "size": 12,
                        "min_size": 8,
                        "fit": "shrink_ellipsis",
                        "color": color,
                        "align": element["align"],
                    }
                )
                y += label_height
                height -= label_height
        lines = value.split("\n") if element["type"] == "text" else [value]
        line_height = max(1, height // len(lines))
        for index, line in enumerate(lines):
            if not line:
                continue
            payload.append(
                {
                    "type": "text_fit",
                    "x": x,
                    "y": y + index * line_height,
                    "width": width,
                    "height": line_height,
                    "value": line,
                    "size": element["font_size"],
                    "min_size": 8,
                    "fit": "shrink_ellipsis",
                    "max_lines": 3 if element["type"] == "text" else 1,
                    "color": color,
                    **(
                        {"background": element["background"]}
                        if element["background"] != "transparent"
                        else {}
                    ),
                    "align": element["align"],
                }
            )

    return payload
