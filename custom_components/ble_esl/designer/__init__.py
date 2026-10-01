"""An optional visual editor layered over the existing render/write pipeline."""

import asyncio
import base64
from functools import partial
from io import BytesIO
import logging
from pathlib import Path
import time

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
import voluptuous as vol

from ..const import DOMAIN
from ..esl_ble.base import DevicePreset
from ..services import build_write_job_from_data, cancel_pending_write, run_ble_write
from .layout import (
    bindings,
    compile_payload,
    sensor_values,
    substitute,
    validate,
    validate_template,
)
from .rendering import render_document, snapshot_layers

KEY = f"{DOMAIN}_designer"
_LOGGER = logging.getLogger(__name__)


class Designer:
    """Persist layouts and subscribe only to each loaded tag's bound entities."""

    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, 1, f"{DOMAIN}.designer")
        self.documents = {}
        self.template_store = Store(hass, 1, f"{DOMAIN}.sensor_templates")
        self.templates = {}
        self.forecast_cache = {}
        self.listeners = {}
        self.timers = {}
        self.last_sent = {}
        self.locks = {}
        self.tasks = {}
        self.render_lock = asyncio.Lock()

    def entry(self, entry_id):
        return next(
            entry
            for entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
            if entry.entry_id == entry_id
        )

    async def save(self, entry, document):
        document = validate(document, entry.runtime_data.preset)
        if document["auto_update"] and not getattr(entry.runtime_data.protocol, "writable", True):
            raise HomeAssistantError("This tag supports discovery only")
        self.documents[entry.entry_id] = document
        await self.store.async_save(self.documents)
        cancel_pending_write(entry.runtime_data)
        self.attach(entry)
        return document

    @callback
    def detach(self, entry_id):
        if task := self.tasks.pop(entry_id, None):
            task.cancel()
        if unsubscribe := self.listeners.pop(entry_id, None):
            unsubscribe()
        if cancel := self.timers.pop(entry_id, None):
            cancel()

    @callback
    def attach(self, entry):
        self.detach(entry.entry_id)
        document = self.documents.get(entry.entry_id)
        if not document or not document["auto_update"]:
            return
        entities = bindings(document)
        if entities:
            self.listeners[entry.entry_id] = async_track_state_change_event(
                self.hass, entities, partial(self.changed, entry.entry_id)
            )
        self.schedule(entry.entry_id)

    @callback
    def changed(self, entry_id, event):
        self.schedule(entry_id)

    @callback
    def schedule(self, entry_id):
        if entry_id in self.timers:
            return
        interval = self.documents[entry_id]["interval"]
        delay = max(2, self.last_sent.get(entry_id, 0) + interval - time.monotonic())

        @callback
        def fire(_now):
            self.timers.pop(entry_id)
            self.tasks[entry_id] = self.hass.async_create_background_task(
                self.auto_send(entry_id), f"ESL designer {entry_id}"
            )

        self.timers[entry_id] = async_call_later(self.hass, delay, fire)

    async def auto_send(self, entry_id):
        try:
            await self.send(self.entry(entry_id), self.documents[entry_id])
        except HomeAssistantError:
            _LOGGER.exception("Automatic display update failed for %s", entry_id)
        finally:
            if self.tasks.get(entry_id) is asyncio.current_task():
                self.tasks.pop(entry_id)

    async def forecasts(self, document):
        needed = {
            (el["entity_id"], "hourly" if el["weather_when"] == "later_today" else "daily")
            for el in document["elements"]
            if el["type"] == "sensor"
            and el["entity_id"].startswith("weather.")
            and el["weather_when"] != "now"
        }
        result = {}
        for entity_id, forecast_type in needed:
            key = (entity_id, forecast_type)
            cached = self.forecast_cache.get(key)
            if not cached or time.monotonic() - cached[0] >= 600:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity_id, "type": forecast_type},
                    blocking=True,
                    return_response=True,
                )
                cached = self.forecast_cache[key] = (
                    time.monotonic(),
                    response[entity_id]["forecast"],
                )
            result[key] = cached[1]
        return result

    async def render(self, preset, document, snapshots):
        # Font/image allocation is expensive on small HA hosts. Keep all designer
        # clients and automatic writes to one render worker at a time.
        async with self.render_lock:
            return await self.hass.async_add_executor_job(
                partial(render_document, self.hass, preset, document, snapshots)
            )

    async def job(self, entry, document):
        document = validate(document, entry.runtime_data.preset)
        forecasts = await self.forecasts(document)
        payload = compile_payload(self.hass, document, self.templates, forecasts)
        service_data = {"payload": payload, "background": document["background"]}
        snapshots = snapshot_layers(self.hass, document, self.templates, forecasts)
        image, layers = await self.render(entry.runtime_data.preset, document, snapshots)
        return (
            await build_write_job_from_data(self.hass, entry, service_data, image=image),
            payload,
            layers,
        )

    async def preview(self, entry, document):
        job, payload, layers = await self.job(entry, document)
        return {
            "png": "data:image/png;base64," + base64.b64encode(job.image_png).decode(),
            "payload": payload,
            "layers": layers,
        }

    async def save_template(self, key, template):
        if not key or ":" not in key:
            raise HomeAssistantError("Choose a sensor type")
        self.templates[key] = validate_template(template)
        await self.template_store.async_save(self.templates)
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            cancel_pending_write(entry.runtime_data)
            self.attach(entry)
        return self.templates[key]

    async def preview_template(self, template, entity_id):
        template = validate_template(template)
        state = self.hass.states.get(entity_id)
        if state is None:
            raise HomeAssistantError("Choose an available sample entity")
        document = substitute(template["document"], sensor_values(state, {}), state.state)
        payload = compile_payload(self.hass, document)
        preset = DevicePreset("template", "Template", template["width"], template["height"], "BWRY")
        snapshots = snapshot_layers(self.hass, document, {}, {})
        image, layers = await self.render(preset, document, snapshots)
        buffer = BytesIO()
        image.save(buffer, "PNG")
        return {
            "png": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
            "payload": payload,
            "layers": layers,
        }

    async def send(self, entry, document):
        if not getattr(entry.runtime_data.protocol, "writable", True):
            raise HomeAssistantError("Minew authentication and image writes are not yet verified")
        generation = entry.runtime_data.write_generation
        async with self.locks.setdefault(entry.entry_id, asyncio.Lock()):
            job, _, _ = await self.job(entry, document)
            job.prevent_duplicate_send = True
            job.generation = generation
            self.last_sent[entry.entry_id] = time.monotonic()
            outcome = await run_ble_write(self.hass, job)
            return outcome.as_response()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ble_esl/designer",
        vol.Required("action"): vol.In(
            ("list", "save", "preview", "send", "templates", "save_template", "preview_template")
        ),
        vol.Optional("entry_id"): str,
        vol.Optional("document"): dict,
        vol.Optional("template"): dict,
        vol.Optional("key"): str,
        vol.Optional("entity_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_designer(hass, connection, msg):
    designer = hass.data[KEY]
    action = msg["action"]
    if action == "templates":
        result = designer.templates
    elif action == "save_template":
        result = await designer.save_template(msg["key"], msg["template"])
    elif action == "preview_template":
        result = await designer.preview_template(msg["template"], msg["entity_id"])
    elif action == "list":
        result = [
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "width": entry.runtime_data.preset.width,
                "height": entry.runtime_data.preset.height,
                "colors": entry.runtime_data.preset.colors,
                "writable": getattr(entry.runtime_data.protocol, "writable", True),
                "document": designer.documents.get(entry.entry_id),
            }
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
    else:
        entry = designer.entry(msg["entry_id"])
        result = await getattr(designer, action)(entry, msg["document"])
    connection.send_result(msg["id"], result)


async def async_setup_designer(hass):
    designer = hass.data[KEY] = Designer(hass)
    designer.documents = await designer.store.async_load() or {}
    designer.templates = await designer.template_store.async_load() or {}
    websocket_api.async_register_command(hass, websocket_designer)
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/ble_esl_designer", str(Path(__file__).parent / "frontend"), False),
            StaticPathConfig(
                "/ble_esl_designer_fonts", str(Path(__file__).parent.parent / "fonts"), True
            ),
        ]
    )
    await panel_custom.async_register_panel(
        hass,
        "ble-esl-designer",
        "ble-esl-designer",
        sidebar_title="Label designer",
        sidebar_icon="mdi:label-outline",
        module_url="/ble_esl_designer/panel.js?v=2",
        require_admin=True,
    )
