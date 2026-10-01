"""The ble_esl.write / ble_esl.write_guarded services and the BLE write pipeline.

A write goes: resolve targets -> render (executor) -> [debounce] -> encode
(executor, started before queueing) -> BLE lock -> connect + transfer with
retries. Services are registered once per Home Assistant instance in
async_setup(); handlers look up the targeted config entries at call time.
"""

from __future__ import annotations

import asyncio
from asyncio import Future, Lock
from collections.abc import Awaitable, Callable, Mapping
import contextlib
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from io import BytesIO
import logging
import time
from typing import Any, Literal, cast

from blesession import Attempt, placement, report_attempt, run_attempts, stages
from blesession.hass import ble_device_or_raise, radio_facts
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.util.dt import now
from PIL import Image

from .const import (
    CONF_DEBOUNCE_MS,
    CONF_MODEL,
    CONF_PREVENT_DUPLICATE_SEND,
    CONF_RETRY_COUNT,
    DATA_LOCK,
    DEFAULT_DEBOUNCE_MS,
    DEFAULT_MODEL,
    DEFAULT_PREVENT_DUPLICATE_SEND,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    SERVICE_WRITE,
    SERVICE_WRITE_GUARDED,
)
from .data import BleEslRuntimeData
from .device import resolve_preset
from .esl_ble import WriteResult
from .esl_ble.base import ATTEMPT_TIMEOUT_S, RETRY_BACKOFF_S, STAGE_MAP, DevicePreset, WriteRefused
from .renderer import render_image
from .types import BleEslConfigEntry

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the domain services (once per HA instance)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE,
        partial(_async_write, hass),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_GUARDED,
        partial(_async_write_guarded, hass),
        supports_response=SupportsResponse.OPTIONAL,
    )


# ── Target resolution ────────────────────────────────────────────────────


async def async_targeted_entries(
    hass: HomeAssistant, service: ServiceCall
) -> list[BleEslConfigEntry]:
    """Resolve a service call's target (entity/device/area/floor/label) to
    the loaded BLE ESL config entries it refers to."""
    entry_ids = await async_extract_config_entry_ids(service)
    # Ids the helper returns for devices/entities of *other* integrations, or
    # targets not in the registries at all, are simply absent here: that is
    # HA's standard target contract (a call is not an error because one of
    # several targets is unknown), so only an all-miss is reported.
    loaded = {entry.entry_id: entry for entry in hass.config_entries.async_loaded_entries(DOMAIN)}
    targets = [loaded[entry_id] for entry_id in sorted(entry_ids) if entry_id in loaded]
    if not targets:
        raise HomeAssistantError(
            "No loaded BLE ESL device matches the service target; "
            "target a BLE ESL device, one of its entities, or its area/label."
        )
    return targets


# ── Outcomes (service response data) ────────────────────────────────────


WriteStatus = Literal[
    "written",
    "failed",
    "scheduled",
    "duplicate",
    "locked",
    "preview",
    "dropped",
]
# The three a guard can return. The rest are produced by the write itself.
_Decline = Literal["locked", "dropped", "duplicate"]


@dataclass
class WriteOutcome:
    """What happened to one target, reported in the service response.

    status:  written    the image is on the tag
             failed     every attempt failed (see error / attempts)
             scheduled  write_guarded: debounced, will run after `delay_ms`;
                        what happens then is not part of the response
             duplicate  write_guarded: unchanged image, not sent
             locked     the write-lock switch is on, not sent
             preview    dry_run: rendered only
             dropped    internal only (a fired debounced write superseded
                        on the lock); never reaches a service response
    """

    status: WriteStatus
    error: str | None = None
    attempts: int | None = None
    duration_s: float | None = None
    delay_ms: int | None = None
    timing: dict[str, float | int | bool | str] | None = None

    def as_response(self) -> dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


class WriteFailed(HomeAssistantError):
    """A write failed after its retries; carries the outcome for the response."""

    def __init__(self, address: str, outcome: WriteOutcome) -> None:
        super().__init__(
            f"Failed to write to {address} after {outcome.attempts} attempts: {outcome.error}"
        )
        self.outcome = outcome


async def _for_each_target(
    hass: HomeAssistant,
    service: ServiceCall,
    handler: Callable[[BleEslConfigEntry], Awaitable[WriteOutcome]],
) -> ServiceResponse:
    """Run handler for every targeted entry, continuing past failures.

    Handlers run concurrently: each renders and starts its encode right
    away and then queues on the BLE lock, which transfers to one tag at a
    time, so later tags encode while an earlier one is transferring. (The
    render step awaits before the lock, so the transfer order is the order
    renders finish, not necessarily the target order.)

    Without a requested response, write failures are collected and raised
    together at the end (one unreachable tag does not prevent the others
    from being written). With `response_variable`, failures are reported
    per target in the response instead of raising, so an automation can
    branch on them. Programming errors always raise.
    """
    targets = await async_targeted_entries(hass, service)
    results = await asyncio.gather(*(handler(entry) for entry in targets), return_exceptions=True)

    outcomes: dict[str, WriteOutcome] = {}
    errors: list[str] = []
    unexpected: list[BaseException] = []
    for entry, result in zip(targets, results, strict=True):
        if isinstance(result, WriteOutcome):
            outcomes[entry.runtime_data.device_id] = result
        elif isinstance(result, WriteFailed):
            outcomes[entry.runtime_data.device_id] = result.outcome
            errors.append(str(result))
        elif isinstance(result, HomeAssistantError):
            outcomes[entry.runtime_data.device_id] = WriteOutcome("failed", error=str(result))
            errors.append(str(result))
        else:
            unexpected.append(result)
    if unexpected:
        # A programming error keeps its traceback; the other tags' write
        # failures are attached so they are not lost from the report.
        if errors:
            unexpected[0].add_note("Other targets failed: " + "; ".join(errors))
        raise unexpected[0]
    if errors and not service.return_response:
        raise HomeAssistantError("; ".join(errors))
    if not service.return_response:
        return None
    return {device_id: outcome.as_response() for device_id, outcome in outcomes.items()}


# ── Write job ────────────────────────────────────────────────────────────


@dataclass
class WriteJob:
    """One rendered image bound for one tag, with the options in force."""

    data: BleEslRuntimeData
    """The entry's runtime data, captured rather than re-read from the entry:
    HA drops entry.runtime_data on unload while a background (debounced)
    write may still be finishing."""
    preset: DevicePreset
    image: Image.Image
    image_png: bytes
    max_retries: int
    prevent_duplicate_send: bool = False
    generation: int | None = None
    """Set for debounced writes; compared under the lock (see run_ble_write)."""
    prepared: Future[Any] | None = field(default=None, repr=False)
    """The encode future, started before queueing on the BLE lock."""

    @property
    def address(self) -> str:
        return self.data.address


async def build_write_job(
    hass: HomeAssistant, entry: BleEslConfigEntry, service: ServiceCall
) -> WriteJob:
    """Render the payload for `entry` and collect the write options.

    The BLE device handle is deliberately not resolved here: it is looked up
    right before each attempt in execute_write, so an unavailable tag goes
    through the same retry/failure path for both services and a debounced
    write never uses a stale handle.
    """
    return await build_write_job_from_data(hass, entry, service.data)


async def build_write_job_from_data(
    hass: HomeAssistant,
    entry: BleEslConfigEntry,
    service_data: Mapping[str, Any],
    *,
    image: Image.Image | None = None,
) -> WriteJob:
    """Render data supplied by a service or the visual designer."""
    data = entry.runtime_data
    options = {**entry.data, **entry.options}
    protocol = data.protocol

    preset = resolve_preset(
        hass, protocol, data.address, options.get(CONF_MODEL, DEFAULT_MODEL)
    ).preset
    data.preset = preset
    data.parser.set_preset(preset)

    if image is None:
        image = await hass.async_add_executor_job(
            partial(
                render_image,
                hass,
                preset,
                service_data.get("payload", ""),
                rotate=service_data.get("rotate", 0),
                background=service_data.get("background", "white"),
            )
        )
    buffer = BytesIO()
    image.save(buffer, "PNG")
    image_png = buffer.getvalue()
    data.preview_coordinator.async_set_updated_data(image_png)
    data.image_store.set_preview(image_png, now())

    return WriteJob(
        data=data,
        preset=preset,
        image=image,
        image_png=image_png,
        max_retries=int(options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)),
    )


# ── Execution ────────────────────────────────────────────────────────────


async def _update_duration_loop(data: BleEslRuntimeData) -> None:
    """Background task to update the duration sensor every second during a write."""
    while True:
        if data.start_time is not None:
            elapsed = round(time.monotonic() - data.start_time, 1)
            data.duration_coordinator.async_set_updated_data(elapsed)
        await asyncio.sleep(1)


def _likely_cause(
    stage: str | None, error: str, facts: dict[str, Any], protocol_id: str
) -> str | None:
    """The tag's own reading of a failure, or None for blesession's generic one.

    Keyed on where the attempt died (`stage`, blesession's primary
    vocabulary), the error text and the protocol. The generic sentences
    (no radio sees the tag, the link never came up, a weak signal) come
    from the library; only what is specific to these tags lives here.
    """
    err = error.lower()
    if "link dropped" in err:
        # The link went away mid-session (blesession ends the wait the moment
        # it does, rather than running the step's timeout out). Nothing about
        # the protocol reads that better than the generic `link_lost`.
        return None
    no_reply = "no response" in err
    where = placement(facts, noun="tag")
    if stage == stages.AUTH:
        if "probes" in err:
            return (
                "The tag did not answer START after connecting (not ready yet); usually transient."
            )
        if no_reply:
            return None
        if "device error 5" in err:
            return "The tag rejected authentication: not a WOLINK tag, or different firmware."
        return "The tag answered the handshake unexpectedly; the protocol or model may not match."
    if stage == stages.TRANSFER:
        if "stalled" in err:
            return f"The tag kept asking for the same part: a marginal link.{where}"
        if no_reply:
            return None
        if "unexpected" in err:
            return "Unexpected reply mid-transfer; the protocol or model may not match this tag."
        return f"The transfer failed: {error or 'unknown error'}.{where}"
    if stage == stages.FINISH:
        # What the tag was expected to say depends on the protocol.
        if "device error" in err:
            return f"The tag reported an error after the transfer: {error}."
        if protocol_id == "xte":
            if no_reply:
                return f"The tag took the image but did not acknowledge the end command.{where}"
            return f"The end of the transfer failed: {error or 'unknown error'}."
        if no_reply:
            return (
                "The tag took the image but did not report the refresh done in time: "
                "a slow panel (cold, large) or a tag-side error."
            )
        return f"The completion wait failed: {error or 'unknown error'}."
    return None


def _report(hass: HomeAssistant, job: WriteJob, attempt: Attempt[WriteResult]) -> dict[str, Any]:
    """The breakdown of one attempt, as the Write Duration / Last Failure
    Time attributes, the diagnostics download and the service response show it."""
    protocol_id = job.data.protocol.id
    return report_attempt(
        attempt,
        operation="write",
        facts=radio_facts(hass, job.address, attempt.trace.link),
        cause=lambda stage, _detail, error, facts: _likely_cause(stage, error, facts, protocol_id),
        noun="tag",
        attempts=job.max_retries,
    )


def _locked(job: WriteJob) -> _Decline | None:
    """The write-lock switch is on."""
    if not job.data.write_lock:
        return None
    _LOGGER.info("Write lock active for %s — skipping BLE write", job.address)
    return "locked"


def _dropped(job: WriteJob) -> _Decline | None:
    """A debounced write whose generation was bumped while it waited."""
    if job.generation is None or job.generation == job.data.write_generation:
        return None
    _LOGGER.debug("Superseded debounced write for %s dropped", job.address)
    return "dropped"


def _duplicate(job: WriteJob) -> _Decline | None:
    """The same payload was already written."""
    if not (job.prevent_duplicate_send and job.image_png == job.data.last_image_data):
        return None
    _LOGGER.info("Skipping duplicate image for %s", job.address)
    return "duplicate"


def _guard(job: WriteJob) -> _Decline | None:
    """Checks that can change while a write waits, run under the BLE lock before every attempt.

    The lock is first because it can flip during the wait, then a superseded
    debounce, then a duplicate of a write that finished ahead of this one.
    The status is what blesession stores as `skipped`, so it stays a plain
    string for the entity attributes and the diagnostics download.
    """
    return _locked(job) or _dropped(job) or _duplicate(job)


async def _attempt(
    hass: HomeAssistant, job: WriteJob, attempt: Attempt[WriteResult]
) -> WriteResult:
    """One BLE attempt: resolve the handle and write; every failure raises."""
    address = job.address
    assert job.prepared is not None, "run_ble_write() schedules the encode"
    # Resolve the handle fresh each attempt: the one seen at service call
    # time may be stale after a debounce delay or a retry sleep. A tag no
    # radio sees raises Unreachable, so it reaches the report with a stage
    # and a likely cause like any other failure.
    ble_device = ble_device_or_raise(hass, address)
    # Packets are paced more only after an attempt that failed *while
    # transferring*: that is what a marginal link looks like. A failure to
    # connect or to get through the handshake is retried at full speed.
    pacing_s = RETRY_BACKOFF_S * attempt.state.get("transfer_failures", 0)
    if pacing_s:
        attempt.trace.note(pacing_s=pacing_s)
    # The encode was started before the BLE lock was taken; the protocol
    # awaits it once the link is up, and a retry awaits the same future
    # again instead of re-encoding.
    return await job.data.protocol.write_prepared(
        ble_device,
        job.preset,
        job.prepared,
        pacing_s=pacing_s,
        trace=attempt.trace,
    )


def _retry(attempt: Attempt[WriteResult]) -> bool:
    """Whether a failed attempt deserves another; also books the pacing."""
    if attempt.timed_out:
        # A timed-out attempt is a dead transport (a proxy gone mid-write);
        # another 10 minutes on the same path helps nobody, and the next
        # automation run is the real retry.
        return False
    if isinstance(attempt.error, WriteRefused):
        # The protocol declined before connecting; nothing about a retry changes that.
        return False
    if attempt.failed_stage == stages.TRANSFER:
        attempt.state["transfer_failures"] = attempt.state.get("transfer_failures", 0) + 1
    return True


async def execute_write(hass: HomeAssistant, job: WriteJob) -> WriteOutcome:
    """Write with retries, tracking duration/connectivity and the result sensors.

    Two locks: the tag's own `write_serial` for the whole write, so two
    writes to one tag never interleave their attempts and sensor state, and
    the domain-wide BLE lock for **one attempt at a time** (blesession's
    run_attempts). Between attempts (the retry pause, or after an attempt
    hit its bound) the BLE lock is free, so a tag that is failing does not
    hold up every other tag for its whole retry sequence.

    Returns the "written" outcome (or a guard's outcome); raises WriteFailed
    after the last failed attempt (a HomeAssistantError carrying the
    "failed" outcome).
    """
    data = job.data
    address = job.address
    ble_lock: Lock = hass.data[DATA_LOCK]
    started = False
    duration_task: asyncio.Task[None] | None = None

    async def guard() -> str | None:
        """Under the BLE lock, before each attempt: the guards, then the
        duration / connectivity sensors on the first attempt that runs."""
        nonlocal started, duration_task
        if (skipped := _guard(job)) is not None:
            return skipped
        if not started:
            started = True
            data.start_time = time.monotonic()
            data.duration_coordinator.async_set_updated_data(0.0)
            data.connectivity_coordinator.async_set_updated_data(True)
            duration_task = asyncio.create_task(_update_duration_loop(data))
        return None

    def on_attempt(attempt: Attempt[WriteResult]) -> None:
        # Every attempt is recorded (with whatever the protocol timed) so the
        # Write Duration sensor's attributes always describe the last one —
        # including an attempt a guard declined, which reports as
        # `success: false` with `skipped: locked` / `duplicate` / `dropped`
        # and so says why nothing was sent.
        data.reports.last = _report(hass, job, attempt)
        _LOGGER.debug("Write to %s timing: %s", address, data.reports.last)
        if attempt.error is not None:
            # Not `attempt.ok`: a declined attempt is not a failure, and the
            # guard has already said why it was skipped.
            _LOGGER.warning(
                "Write failed to %s (attempt %d/%d): %s",
                address,
                attempt.number,
                job.max_retries,
                attempt.error,
            )

    async with data.write_serial:
        try:
            last = await run_attempts(
                partial(_attempt, hass, job),
                lock=ble_lock,
                max_attempts=job.max_retries,
                attempt_timeout_s=ATTEMPT_TIMEOUT_S,
                pause_s=1.0,
                retry_if=_retry,
                guard=guard,
                on_attempt=on_attempt,
                stage_map=STAGE_MAP,
                name=f"write to {address}",
            )
            if last.skipped is not None:
                if not started:
                    # Declined on arrival — no attempt ran, so nothing here
                    # touched the duration sensor, and the entity rewrites
                    # its attributes only when its coordinator fires. Wake it
                    # once with the value it already has: `async_set_updated_data`
                    # notifies listeners whether or not the value changed, so
                    # the `skipped` report on_attempt just filed reaches the
                    # entity instead of sitting in reports.last, where only
                    # the diagnostics download would find it. The state stays
                    # the last real write's duration; nothing was written now.
                    duration = data.duration_coordinator
                    duration.async_set_updated_data(duration.data)
                # blesession types `skipped` as Any. The guard only returns _Decline.
                return WriteOutcome(cast(_Decline, last.skipped))
            timing = data.reports.last
            if last.ok:
                result = last.result
                assert result is not None
                # Session-based protocols (e.g. easyTag) report battery/temp
                # in the write result; others update passively from adverts.
                if result.battery_mv is not None:
                    data.battery_coordinator.async_set_updated_data(result.battery_mv / 1000.0)
                if result.temperature_c is not None:
                    data.temperature_coordinator.async_set_updated_data(result.temperature_c)
                data.image_coordinator.async_set_updated_data(job.image_png)
                # Only a successful write counts for duplicate detection; a
                # failed or locked-out write must not suppress a retry of
                # the same payload.
                data.last_image_data = job.image_png
                data.image_store.set_written(job.image_png, now())
                return WriteOutcome(
                    "written",
                    attempts=last.number,
                    duration_s=round(time.monotonic() - data.start_time, 2),
                    timing=timing,
                )

            data.failure_coordinator.async_set_updated_data(
                (data.failure_coordinator.data or 0) + 1
            )
            # Filed in both slots here, not from on_attempt: `last_failure`
            # means the write that failed with every retry exhausted, which
            # is what the timestamp beside it records. A copy, so nothing
            # that later touches the report in place can change it.
            data.reports.record(dict(timing or {}))
            data.last_failure_coordinator.async_set_updated_data(now())
            assert last.error is not None
            raise WriteFailed(
                address,
                WriteOutcome(
                    "failed",
                    error=str(last.error) or type(last.error).__name__,
                    attempts=last.number,
                    duration_s=round(time.monotonic() - data.start_time, 2),
                    timing=timing,
                ),
            )
        finally:
            if started:
                assert duration_task is not None
                duration_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await duration_task
                if data.start_time is not None:
                    data.duration_coordinator.async_set_updated_data(
                        round(time.monotonic() - data.start_time, 2)
                    )
                data.start_time = None
                data.connectivity_coordinator.async_set_updated_data(False)


async def run_ble_write(hass: HomeAssistant, job: WriteJob) -> WriteOutcome:
    """Encode, then write.

    The encode runs once per write, in HA's executor, *before* queueing on
    the locks: tags waiting their turn encode while another transfers, and
    the CPU-bound work never runs on the event loop. The protocol awaits the
    future only once its link is up (overlapping connect), and every retry
    attempt reuses the same result.
    """
    data = job.data
    prepared = hass.async_add_executor_job(
        data.protocol.prepare_image, job.preset, job.image, data.address
    )
    job.prepared = prepared
    try:
        return await execute_write(hass, job)
    finally:
        # Skipped or failed before the encode was awaited: drop it without
        # a "Future exception was never retrieved" warning.
        if not prepared.done():
            prepared.cancel()
        elif not prepared.cancelled():
            prepared.exception()


# ── Debounce ─────────────────────────────────────────────────────────────


@callback
def cancel_pending_write(data: BleEslRuntimeData) -> None:
    """Cancel a pending debounced write (new request or immediate path).

    Bumping the generation also invalidates a debounced write whose timer
    has already fired but which is still waiting for the BLE lock, so a
    cancelled payload is never sent after a newer one was requested.
    """
    data.write_generation += 1
    if data.pending_write_cancel is not None:
        data.pending_write_cancel()
        data.pending_write_cancel = None


@callback
def schedule_debounced_write(hass: HomeAssistant, job: WriteJob, delay_s: float) -> None:
    """(Re)schedule a write to run `delay_s` after this call.

    Any pending write for the entry is cancelled first, so repeated calls
    collapse into one write carrying the last payload, sent once requests
    have been quiet for the debounce delay (trailing edge). The write runs
    as a background task; the service call itself returns immediately.
    """
    data = job.data
    address = job.address
    cancel_pending_write(data)
    job.generation = data.write_generation

    async def _run() -> None:
        try:
            await run_ble_write(hass, job)
        except HomeAssistantError as err:
            # No service caller to propagate to; the failure sensors are
            # already updated by execute_write.
            _LOGGER.error("Debounced write to %s failed: %s", address, err)

    @callback
    def _fire(_now: datetime) -> None:
        data.pending_write_cancel = None
        hass.async_create_background_task(_run(), name=f"ble_esl debounced write {address}")

    data.pending_write_cancel = async_call_later(hass, delay_s, _fire)


# ── Service handlers ─────────────────────────────────────────────────────


async def _async_write(hass: HomeAssistant, service: ServiceCall) -> ServiceResponse:
    """ble_esl.write: always send (unless dry_run)."""
    dry_run = service.data.get("dry_run", False)

    async def handle(entry: BleEslConfigEntry) -> WriteOutcome:
        job = await build_write_job(hass, entry, service)
        if dry_run:
            return WriteOutcome("preview")
        cancel_pending_write(job.data)
        return await run_ble_write(hass, job)

    return await _for_each_target(hass, service, handle)


async def _async_write_guarded(hass: HomeAssistant, service: ServiceCall) -> ServiceResponse:
    """ble_esl.write_guarded: duplicate guard, write lock, debounce, then send."""
    dry_run = service.data.get("dry_run", False)

    async def handle(entry: BleEslConfigEntry) -> WriteOutcome:
        job = await build_write_job(hass, entry, service)
        data = job.data
        options = {**entry.data, **entry.options}
        job.prevent_duplicate_send = bool(
            options.get(CONF_PREVENT_DUPLICATE_SEND, DEFAULT_PREVENT_DUPLICATE_SEND)
        )

        if (status := _duplicate(job)) is not None:
            return WriteOutcome(status)
        if dry_run:
            # Preview only (README): leaves duplicate detection untouched.
            return WriteOutcome("preview")
        if (status := _locked(job)) is not None:
            return WriteOutcome(status)

        debounce_ms = int(
            service.data.get(
                "debounce_override_ms",
                options.get(CONF_DEBOUNCE_MS, DEFAULT_DEBOUNCE_MS),
            )
        )
        if debounce_ms > 0:
            if data.pending_write_cancel is not None:
                _LOGGER.info(
                    "Cancelled pending write for %s, rescheduled with %dms delay",
                    job.address,
                    debounce_ms,
                )
            schedule_debounced_write(hass, job, debounce_ms / 1000.0)
            return WriteOutcome("scheduled", delay_ms=debounce_ms)
        cancel_pending_write(data)
        return await run_ble_write(hass, job)

    return await _for_each_target(hass, service, handle)
