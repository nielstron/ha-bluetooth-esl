"""Render movable editor layers with the exact same pixels used for writes."""

import base64
from copy import deepcopy
from io import BytesIO

from PIL import Image, ImageChops

from ..esl_ble.base import DevicePreset
from ..renderer import render_image
from .layout import compile_payload


def snapshot_layers(hass, document, templates, forecasts):
    """Resolve HA state on the event loop, before CPU work enters the executor."""
    layers = []
    for element in document["elements"]:
        local = deepcopy(element)
        local["x"] = local["y"] = 0
        payload = compile_payload(hass, {"elements": [local]}, templates, forecasts)
        layers.append((element, payload))
    return layers


def png_url(image):
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def render_document(hass, preset, document, snapshots):
    """Compose opaque e-paper output and transparent, independently movable layers.

    imagespec returns RGB. Rendering against black and white identifies untouched
    pixels without mistaking intentionally white text or fills for transparency.
    Font drawing uses imagespec's monochrome masks, so covered pixels are exact.
    """
    canvas = Image.new("RGB", (preset.width, preset.height), document["background"])
    previews = {}
    for element, payload in snapshots:
        local = DevicePreset("layer", "Layer", element["width"], element["height"], preset.colors)
        light = render_image(hass, local, payload, background="white")
        dark = render_image(hass, local, payload, background="black")
        alpha = (
            ImageChops.difference(light, dark).convert("L").point(lambda value: 0 if value else 255)
        )
        layer = light.convert("RGBA")
        layer.putalpha(alpha)
        canvas.paste(layer, (element["x"], element["y"]), layer)
        previews[element["id"]] = png_url(layer)
    return canvas, previews
