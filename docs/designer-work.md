# Designer work

Updated 2026-10-01. Checked items are implemented. Latest batch installed and live checks completed.

- [x] Remove preset display layouts.
- [x] Refresh/save/send/undo/redo use icons with accessible names and tooltips.
- [x] Independently collapse panels; hamburger controls in each panel's top-right corner, with reopen controls when collapsed.
- [x] Delete button on the selected element's top-right corner; Delete/Backspace shortcuts respect text editing.
- [x] Duplicate/delete/send back/bring front/centre moved into a right-click menu with icons and text.
- [x] Dedicated sensor-type template editor; drag/resize/layers, name/state/unit/icon parts and visibility for a specific state.
- [x] Entity icon overrides and device-class/state icons; weather conditions render as icons instead of raw "cloudy" strings.
- [x] Searchable icon picker, palette swatches (including transparent) and alignment icons.
- [x] Sensor/text backgrounds default to transparent, with opaque palette choices available.
- [x] Text/label/number properties update without blur or Enter.
- [x] Inline text editing on the preview; Escape finishes editing.
- [x] Boxes may extend beyond the tag; the output is cropped to the physical display.
- [x] Auto update sensor option moved next to Send, with its interval there.
- [x] Weather time/value controls: now/later today/tomorrow/+2/+3 days; condition/temperature/low/precipitation/chance/wind/humidity.
- [x] Temperature glyph diagnosis: an integration reports superscript-zero "⁰C", unsupported by the font. Normalize temperature units to "°C". Reproduced before fixing; verified on live HA.
- [x] Register editor icon/text fonts through FontFace rather than shadow-DOM @font-face. Missing icon-picker glyphs reproduced in a browser test before fixing.
- [x] Aligning live editing and pixel output: use the same rendered element images for editing and final composition, including wrapping.
- [x] Label override beside Show label, visible only when checked; Show unit/decimals grouped, decimals only for numeric entities.
- [x] Independent Layers / Background card outside the selected element properties.
- [x] Searchable HA entity dropdown with icon and formatted current-state preview.
- [x] “＋ Create template” in the template picker; preselect originating sensor type/sample, name/save a custom template and apply it to that element.
- [x] Final shape dropdown tests, renderer/layer consistency tests, desktop/mobile QA and installation of latest batch.

First deployment verified on live HA: corrected degree glyph, tomorrow's temperature via HA weather forecast service, template preview, context-menu duplication/Backspace/trash, collapsed panels. Latest additions are deployed.

Further numerical formatting choices remain a future extension. Minew image writing is still unverified. GitHub fork changes are not published yet; installation is a direct custom component.

- [x] Remove redundant Preview button: previews render automatically.
- [x] Sensor template mode hides tag Send/Refresh/Auto update controls.
- [x] Choose a concrete sample sensor first, showing current state; no device-class filtering hides threshold sensors.
- [x] Reusable template compatibility follows binary/numeric/text/weather output; named custom templates are offered to comparable sensors. Legacy saved templates remain readable.
- [x] Explicit text line breaks survive pixel rendering (regression reproduced before fixing).

Validation: 359 Python tests and 19 browser tests passed. Exact layer composition, transparent overlays, cropping and all five shape choices are covered.

- [x] Uploaded image elements with contain/fill/stretch, layers, resizing and visibility for a chosen sensor state.
- [x] Explicit state → icon map on icon template parts: On/Off rows, custom state rows, per-row icon picker and HA icon fallback. The old visibility field is removed for icons.
- [x] Numeric output defaults work across device classes; regression verified before/after fixing fallback resolution.
- [x] Live HA found `binary_sensor.laundry_laundry_vibration_laundry_running`; sample choices include it. Include number/input_boolean/select/input_select entities too.

Live HA v2 verification passed with no page errors: sensor degree units, tomorrow forecast, right-click duplication/deletion, correct icon picker glyphs and collapsed panels. Final image/state-map increment is installed.

- [x] Slow-host preview throttling: one in-flight request per editor, coalesce superseded edits, 200 ms debounce; shared backend render lock. Regression reproduced four overlapping requests before the fix and one after.

Pi incident: host stalled after first successful live QA; stopped all transfer/browser work. User reboot restored SSH. Host has 905 MiB RAM and uses swap during HA startup. Previous kernel journal not retained; cause unconfirmed. Latest state/image/preview-throttling increment is installed and verified.

Final live check: selected the actual laundry binary sensor, created an unsaved custom template draft, mapped on → mdi:washing-machine and off → mdi:washing-machine-off, verified exact pixel preview and mapping pickers visually. Send/Preview absent in template mode; no browser errors. No templates/documents saved during QA and no physical tag writes. Pi remained responsive after the check (uptime 7 min, 640 MiB available, 125 MiB swap used).
