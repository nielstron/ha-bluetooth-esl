import {
  clone,
  createId,
  palette,
  emptyDocument,
  clampBox,
  newElement,
} from "./model.js";
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${name === "menu" ? '<path d="M4 6h16M4 12h16M4 18h16"/>' : '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>'}</svg>`;
const shapeTypes = [
  "rectangle",
  "rounded_rectangle",
  "ellipse",
  "triangle",
  "line",
];
const toolIcon = (name) =>
  `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${
    {
      duplicate:
        '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
      back: '<path d="m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5"/>',
      front: '<path d="m3 16 9 5 9-5-9-5-9 5Zm0-5 9-5 9 5M3 6l9-5 9 5"/>',
      center: '<path d="M12 2v20M3 6h18M6 12h12M3 18h18"/>',
      text: '<path d="M4 4h16M12 4v16M8 20h8"/>',
      shape: '<rect x="4" y="4" width="16" height="16" rx="2"/>',
      image:
        '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="2"/><path d="m3 18 6-6 4 4 3-4 5 6"/>',
      icon: '<path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/>',
      reload: '<path d="M20 7v5h-5M20 12a8 8 0 1 0-2 6"/>',
      save: '<path d="M4 3h13l4 4v14H3V3h1M7 3v6h9V3M7 21v-8h10v8"/>',
      preview:
        '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
      send: '<path d="m7 7 10 10-5 4V3l5 4L7 17"/>',
      undo: '<path d="M8 4 3 9l5 5M3 9h10a7 7 0 0 1 0 14"/>',
      redo: '<path d="m16 4 5 5-5 5M21 9H11a7 7 0 0 0 0 14"/>',
    }[name]
  }</svg>`;
const iconFont = new FontFace(
  "LabelMDI",
  "url(/ble_esl_designer_fonts/materialdesignicons-webfont.ttf)",
)
  .load()
  .then((font) => document.fonts.add(font));
const textFont = new FontFace(
  "LabelText",
  "url(/ble_esl_designer_fonts/NotoSansKR-Regular.ttf)",
)
  .load()
  .then((font) => document.fonts.add(font));
const style = `
.mdi{font-family:LabelMDI;line-height:1;display:inline-block;font-weight:normal;font-style:normal}.icon-popover{margin-top:8px}.icon-popover .icon-picker{margin-top:8px}.icon-choice{display:flex;align-items:center;gap:8px;width:100%;text-align:left}.toolbar .icon-button{border:1px solid var(--divider-color,#cbd3de)}:host{display:block;color:var(--primary-text-color,#18232f);background:var(--primary-background-color,#f5f7fa);font:14px system-ui;height:100%;overflow:auto}*{box-sizing:border-box}header{display:flex;align-items:center;gap:14px;padding:18px 24px;background:var(--card-background-color,white);border-bottom:1px solid var(--divider-color,#e0e5eb)}h1{font-size:21px;margin:0}header span{color:var(--secondary-text-color,#637083)}button,input,select,textarea{font:inherit;color:inherit;background:var(--card-background-color,white);border:1px solid var(--divider-color,#cbd3de);border-radius:6px;padding:8px}button{cursor:pointer}button:hover{border-color:#257d86}button:disabled{opacity:.45;cursor:default}button.primary{background:#166d75;color:white;border-color:#166d75}button:focus-visible,input:focus-visible,select:focus-visible,.el:focus-visible{outline:2px solid #167c88;outline-offset:2px}.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 24px}.toolbar select{max-width:360px}.editor-bar{display:flex;align-items:center;gap:12px;padding:0 24px 12px}.editor-bar .spacer{flex:1}.icon-button{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;padding:7px;border:0;background:transparent}.icon-button[aria-expanded="true"]{background:var(--secondary-background-color,#e9eff2)}.icon-button.danger:hover{color:#c33;background:#c331}.context-menu{position:fixed;z-index:1000;width:220px;padding:6px;background:var(--card-background-color,white);box-shadow:0 5px 24px #0003;border:1px solid var(--divider-color,#ddd);border-radius:8px}.context-menu button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:0}.context-menu kbd{margin-left:auto}.panel-heading{display:flex;align-items:center;gap:8px;margin-bottom:14px}.panel-heading h2{flex:1;margin:0}.delete-handle{position:absolute;right:0;top:-24px;width:24px;height:24px;display:flex;align-items:center;justify-content:center;padding:2px;border:1px solid #16838c;color:#b33;background:var(--card-background-color,white);z-index:5;border-radius:4px}.delete-handle svg{width:18px;height:18px}.context-menu kbd{float:right;font-size:11px;color:var(--secondary-text-color,#637083)}.template-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:0 24px 14px}.template-controls input[type="number"]{width:75px}.tabs{display:flex;gap:4px;margin-left:auto}.tabs button[aria-pressed="true"]{background:#166d75;color:white}.tile-icon{position:absolute;left:4px;top:10px;width:36px;height:36px;display:flex;align-items:center;justify-content:center}.tile-copy{margin-left:48px;padding:6px 0}.tile-copy .value{font-size:18px}.el ha-icon{--mdc-icon-size:32px}.el.icon-content ha-icon{--mdc-icon-size:inherit}.state-rules{margin:0}.template-note{margin:0 24px 12px}.picker{display:flex;gap:5px;flex-wrap:wrap}.swatch{width:28px;height:28px;padding:0;background:var(--swatch);border:1px solid #888;border-radius:50%}.swatch[aria-pressed="true"]{outline:2px solid #16838c;outline-offset:2px}.align-button{width:32px;height:32px;padding:5px}.align-button[aria-pressed="true"]{background:#16838c22;border-color:#16838c}.align-button svg{width:20px;height:20px}.icon-picker{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;max-height:200px;overflow:auto}.icon-picker button{padding:6px}.icon-picker ha-icon{--mdc-icon-size:24px}.state-rules input{width:100%}.muted.help{display:none}.canvas-wrap + p{display:none}.workspace{display:grid;grid-template-columns:240px minmax(320px,1fr) 260px;gap:18px;padding:0 24px 24px}.workspace.library-closed{grid-template-columns:minmax(0,1fr) 260px}.workspace.inspector-closed{grid-template-columns:240px minmax(0,1fr)}.workspace.library-closed.inspector-closed{grid-template-columns:minmax(0,1fr)}.workspace.library-closed .library,.workspace.inspector-closed .inspector{display:none}.card{min-width:0;background:var(--card-background-color,white);border:1px solid var(--divider-color,#dfe5eb);border-radius:10px;padding:16px}h2{font-size:15px;margin:0 0 14px}p{line-height:1.5}.muted{color:var(--secondary-text-color,#637083);font-size:12px}.entity-preview{margin:12px 0 20px}.entity-state{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:8px}.entity-state .state-copy{flex:1;min-width:0}.entity-state .state-name{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.entity-state .state-value{font-size:18px;margin-top:4px}.entity-state ha-state-icon{--mdc-icon-size:28px}.entity-state button{flex:none}ha-entity-picker{display:block;width:100%;margin-bottom:12px}.entity{display:block;text-align:left;width:100%;margin:5px 0}.entity small{display:block;color:var(--secondary-text-color,#637083);font-size:11px;overflow:hidden;text-overflow:ellipsis}.entity[draggable]{cursor:grab}.tools{display:flex;flex-wrap:wrap;gap:6px}.canvas-wrap{min-width:0;overflow:auto;height:420px;min-height:0;display:flex;align-items:center;justify-content:flex-start;background:repeating-conic-gradient(#edf0f4 0% 25%,#f6f8fa 0% 50%) 50%/16px 16px;border-radius:6px;padding:30px}.stage-space{margin:auto;flex:none;position:relative}.stage{position:relative;transform-origin:top left;background:white;color:black;box-shadow:0 8px 24px #15293825;outline:1px solid #c5ced9;touch-action:none}.el{position:absolute;overflow:visible;cursor:move;outline:1px dashed transparent;touch-action:none;user-select:none}.el:hover{outline:1px dashed #1c8990}.el.selected{outline:1px solid #16838c}.el .content{height:100%;overflow:hidden;font-family:LabelText, sans-serif}.el.editing .content{visibility:visible!important;user-select:text;cursor:text;white-space:pre-wrap;outline:0}.el.rendered .content{visibility:hidden}.layer-preview{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;image-rendering:pixelated}.el.editing .layer-preview,.stage.exact-mode .layer-preview{display:none}.label{font-size:12px;height:18px;white-space:nowrap;overflow:hidden}.value{white-space:nowrap;overflow:hidden}.handle{position:absolute;right:-3px;bottom:-3px;width:6px;height:6px;background:#16838c;cursor:nwse-resize;z-index:3}.exact{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;image-rendering:pixelated}.stage.exact-mode .content{visibility:hidden}.stage.exact-mode .el{background:transparent!important}.stage.exact-mode .el.selected{z-index:100}.status{min-height:24px;padding:0 24px 12px;color:var(--secondary-text-color,#637083)}.error{color:#c33}.props{display:grid;grid-template-columns:1fr 1fr;gap:9px}.props label{font-size:12px;display:flex;flex-direction:column;gap:5px}.props label.check{flex-direction:row;align-items:center}.props .wide{grid-column:1/-1}.props input,.props select,.props textarea{width:100%;min-width:0}.check{display:flex;align-items:center;gap:7px;margin:12px 0}.check input{width:auto}.layers{margin-top:16px;max-height:150px;overflow:auto}.layer{display:block;width:100%;text-align:left;margin:4px 0}.layer.active{border-color:#16838c}.side-column{display:flex;flex-direction:column;gap:18px}.side-column .layers{margin-top:0}.footer-tools{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}@media(max-width:1050px){.workspace{grid-template-columns:200px 1fr}.inspector{grid-column:1/-1}.props{grid-template-columns:repeat(4,1fr)}}@media(max-width:650px){.workspace.library-closed,.workspace.inspector-closed,.workspace.library-closed.inspector-closed{grid-template-columns:minmax(0,1fr)}header,.toolbar,.editor-bar,.template-controls{padding:12px}header{flex-wrap:wrap}header span{display:none}.workspace{padding:0 12px 12px;grid-template-columns:minmax(0,1fr)}.library,.inspector{grid-column:auto}.entities{height:150px}.canvas-wrap{height:300px}.props{grid-template-columns:1fr 1fr}}
`;

export class BleEslDesigner extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.tags = [];
    this.document = emptyDocument();
    this.selected = null;
    this.undoStack = [];
    this.redoStack = [];
    this.zoom = 1;
    this.zoomMode = "fit";
    this.resizeObserver = new ResizeObserver(() => this.fitPreview());
    this.search = "";
    this.libraryEntity = "";
    this.status = "";
    this.preview = null;
    this.layerPreviews = {};
    this.dirty = false;
    this.busy = false;
    this.previewSequence = 0;
    this.drafts = new Map();
    this.libraryOpen = true;
    this.inspectorOpen = true;
    this.templates = {};
    this.icons = {};
    this.templateDrafts = new Map();
    this.sampleEntity = "";
    this.mode = "display";
    this.templateKey = "output:numeric";
    this.shadowRoot.addEventListener("contextmenu", (event) =>
      this.contextMenu(event),
    );
    this.shadowRoot.addEventListener("pointerdown", (event) => {
      if (!event.target.closest(".context-menu")) this.closeContextMenu();
    });
    this.shadowRoot.addEventListener("click", (event) => this.click(event));
    this.shadowRoot.addEventListener("change", (event) => this.change(event));
    this.shadowRoot.addEventListener("input", (event) => this.input(event));
    this.shadowRoot.addEventListener("focusout", (event) => {
      this.typingProperty = null;
      if (event.target.dataset.editText) this.finishTextEdit();
    });
    this.shadowRoot.addEventListener("keydown", (event) => this.key(event));
    this.shadowRoot.addEventListener("pointerdown", (event) =>
      this.pointer(event),
    );
    this.shadowRoot.addEventListener("dragstart", (event) => {
      const button = event.target.closest("[data-entity]");
      if (button)
        event.dataTransfer.setData("text/plain", button.dataset.entity);
    });
    this.shadowRoot.addEventListener("dragover", (event) => {
      if (event.target.closest(".stage")) event.preventDefault();
    });
    this.shadowRoot.addEventListener("drop", (event) => this.drop(event));
  }
  set hass(value) {
    const previous = this._hass;
    this._hass = value;
    this.renderEntityPreview();
    const picker = this.shadowRoot.querySelector("ha-entity-picker");
    if (picker) picker.hass = value;
    if (this.isConnected && !this.started) this.boot();
    else if (
      this.tag &&
      !this.gesture &&
      ((this.mode === "template" &&
        previous?.states[this.sampleEntity] !==
          value.states[this.sampleEntity]) ||
        this.document.elements.some(
          (element) =>
            element.type === "sensor" &&
            previous?.states[element.entity_id] !==
              value.states[element.entity_id],
        ))
    ) {
      this.drawStage();
      this.queuePreview();
    }
  }
  get hass() {
    return this._hass;
  }
  connectedCallback() {
    this.render();
    if (this.hass && !this.started) this.boot();
  }
  disconnectedCallback() {
    clearTimeout(this.previewTimer);
    this.previewSequence++;
    this.gesture?.abort();
    this.resizeObserver.disconnect();
  }
  async boot() {
    this.started = true;
    try {
      await Promise.all([
        iconFont,
        textFont,
        customElements.whenDefined("ha-entity-picker"),
      ]);
      this.icons = await fetch(new URL("./icons.json", import.meta.url)).then(
        (response) => response.json(),
      );
      this.templates = await this.api("templates");
      this.tags = await this.api("list");
      this.mode = "display";
      this.tag = this.tags[0];
      if (this.tag) this.load(this.tag);
      else {
        this.status =
          "Add a BLE ESL device in Settings → Devices & services first.";
        this.render();
      }
    } catch (error) {
      this.report(error);
    }
  }
  api(action, extra = {}) {
    return this.hass.callWS({ type: "ble_esl/designer", action, ...extra });
  }
  load(tag) {
    if (this.tag && this.dirty)
      this.drafts.set(this.tag.entry_id, clone(this.document));
    this.tag = tag;
    this.document = clone(
      this.drafts.get(tag.entry_id) || tag.document || emptyDocument(),
    );
    this.selected = null;
    this.undoStack = [];
    this.redoStack = [];
    this.dirty = this.drafts.has(tag.entry_id);
    this.preview = null;
    this.layerPreviews = {};
    this.status = tag.writable
      ? "Ready"
      : "Discovery only: preview is available; sending is not supported yet.";
    this.render();
    this.queuePreview();
  }
  checkpoint() {
    this.undoStack.push(clone(this.document));
    if (this.undoStack.length > 100) this.undoStack.shift();
    this.redoStack = [];
  }
  edited(render = true) {
    this.dirty = true;
    this.preview = null;
    this.previewSequence++;
    if (render) this.render();
    else this.drawStage();
    this.queuePreview();
  }
  report(error) {
    this.status = error.message || String(error);
    this.error = true;
    this.renderStatus();
  }
  renderStatus() {
    const node = this.shadowRoot.querySelector(".status");
    if (node) {
      node.textContent = this.status;
      node.classList.toggle("error", !!this.error);
    }
  }
  get element() {
    return this.document.elements.find(
      (element) => element.id === this.selected,
    );
  }
  entities() {
    return Object.values(this.hass?.states || {}).filter((state) =>
      /^(sensor|binary_sensor|weather|input_number|number|input_boolean|input_select|select|counter)\./.test(
        state.entity_id,
      ),
    );
  }
  entityName(state) {
    return (
      this.hass.formatEntityName?.(state) ||
      state.attributes.friendly_name ||
      state.entity_id
    );
  }
  value(element) {
    if (element.type === "text") return element.text;
    const state = this.hass.states[element.entity_id];
    if (!state) return "Unavailable";
    if (
      element.decimals !== undefined &&
      !["unknown", "unavailable"].includes(state.state)
    )
      return (
        Number(state.state).toFixed(element.decimals) +
        (element.show_unit && state.attributes.unit_of_measurement
          ? " " + state.attributes.unit_of_measurement
          : "")
      );
    const formatted = this.hass.formatEntityState?.(state) || state.state;
    if (!element.show_unit && state.attributes.unit_of_measurement)
      return state.state;
    return formatted;
  }
  sensorType(state) {
    return (
      state.entity_id.split(".")[0] +
      ":" +
      (state.attributes.device_class || "default")
    );
  }
  sampleState() {
    return this.hass.states[this.sampleEntity];
  }
  defaultTemplate() {
    const tag = { width: 140, height: 60, colors: "BWRY" };
    const make = (type, fields) => ({ ...newElement(type, tag), ...fields });
    return {
      ...emptyDocument(),
      elements: [
        make("icon", { x: 4, y: 14, width: 32, height: 32, icon: "{{icon}}" }),
        make("text", {
          x: 44,
          y: 4,
          width: 92,
          height: 18,
          font_size: 12,
          text: "{{name}}",
        }),
        make("text", {
          x: 44,
          y: 25,
          width: 92,
          height: 31,
          font_size: 20,
          text: "{{state}} {{unit}}",
        }),
      ],
    };
  }
  outputType(state) {
    if (!state) return "text";
    if (state.entity_id.startsWith("weather.")) return "weather";
    if (
      state.entity_id.startsWith("binary_sensor.") ||
      ["on", "off"].includes(state.state)
    )
      return "binary";
    return (state.state.trim() !== "" &&
      Number.isFinite(Number(state.state))) ||
      state.attributes.unit_of_measurement
      ? "numeric"
      : "text";
  }
  templateCompatibility(template, key) {
    const type = template?.sensor_type || key;
    if (type.startsWith("output:")) return type.split(":")[1];
    if (type.startsWith("binary_sensor:")) return "binary";
    if (type.startsWith("weather:")) return "weather";
    return "numeric";
  }
  templateTypes() {
    return [
      ...new Set([
        "output:numeric",
        "output:binary",
        "output:text",
        "output:weather",
        ...Object.keys(this.templates),
        ...this.templateDrafts.keys(),
      ]),
    ];
  }
  templateControls() {
    if (this.mode !== "template") return "";
    const samples = this.entities();
    return `<div class="template-controls"><label>Sensor <select id="template-sample" aria-label="Sample sensor">${samples.map((state) => `<option value="${esc(state.entity_id)}" ${state.entity_id === this.sampleEntity ? "selected" : ""}>${esc(this.entityName(state))} · ${esc(state.state)}</option>`).join("")}</select><span class="muted">${this.outputType(this.sampleState())} output</span></label><label>Name <input id="template-name" aria-label="Template name" value="${esc(this.templateName)}"></label><label>Template <select id="template-type" aria-label="Template">${this.templateTypes()
      .map(
        (key) =>
          `<option value="${esc(key)}" ${key === this.templateKey ? "selected" : ""}>${esc(this.templates[key]?.name || this.templateDrafts.get(key)?.name || (key.startsWith("output:") ? key.split(":")[1] + " template" : key.replace(":", " · ")))}</option>`,
      )
      .join(
        "",
      )}</select></label><label>W <input id="template-width" aria-label="Template width" type="number" min="16" max="1000" value="${this.tag?.width}"></label><label>H <input id="template-height" aria-label="Template height" type="number" min="16" max="1000" value="${this.tag?.height}"></label></div>`;
  }
  templateParts() {
    if (this.mode !== "template") return "";
    return `<div class="tools">${["name", "state", "unit"].map((name) => `<button data-token="${name}">${name[0].toUpperCase() + name.slice(1)}</button>`).join("")}<button data-action="add-state-icon">State icon</button></div>`;
  }
  switchMode(mode) {
    if (mode === this.mode) return;
    if (mode === "template") {
      this.displaySession = {
        tag: this.tag,
        document: this.document,
        selected: this.selected,
        dirty: this.dirty,
        undo: this.undoStack,
        redo: this.redoStack,
      };
      this.mode = mode;
      this.loadTemplate(this.templateKey);
    } else {
      this.rememberTemplate();
      this.mode = mode;
      const session = this.displaySession;
      this.tag = session.tag;
      this.document = session.document;
      this.selected = session.selected;
      this.dirty = session.dirty;
      this.undoStack = session.undo;
      this.redoStack = session.redo;
      this.preview = null;
      this.layerPreviews = {};
      this.render();
      this.queuePreview();
    }
  }
  rememberTemplate() {
    if (this.mode === "template" && this.tag)
      this.templateDrafts.set(this.templateKey, {
        width: this.tag.width,
        height: this.tag.height,
        document: clone(this.document),
        name: this.templateName,
        sensor_type: this.templateSensorType,
        dirty: this.dirty,
      });
  }
  loadTemplate(key) {
    if (this.tag?.title === this.templateKey) this.rememberTemplate();
    this.templateKey = key;
    const template = this.templateDrafts.get(key) ||
      this.templates[key] || {
        width: 140,
        height: 60,
        document: this.defaultTemplate(),
        dirty: false,
      };
    this.tag = {
      width: template.width,
      height: template.height,
      colors: "BWRY",
      title: key,
      writable: false,
    };
    this.layerPreviews = {};
    this.templateName =
      template.name || key.startsWith("output:")
        ? key.split(":")[1] + " template"
        : key.replace(":", " · ");
    this.templateSensorType =
      template.sensor_type || key.split(":").slice(0, 2).join(":");
    this.document = clone(template.document);
    if (
      !this.templates[key] &&
      !this.templateDrafts.has(key) &&
      /^(binary_sensor|weather):|^output:(binary|weather)/.test(key)
    )
      this.document.elements = this.document.elements.filter(
        (el) => el.text !== "{{state}} {{unit}}",
      );
    this.dirty = !!template.dirty;
    this.sampleEntity =
      this.entities().find(
        (state) =>
          this.outputType(state) === this.templateCompatibility(template, key),
      )?.entity_id ||
      this.entities().find(
        (state) =>
          state.entity_id.split(".")[0] ===
          this.templateSensorType.split(":")[0],
      )?.entity_id ||
      "";
    this.selected = null;
    this.undoStack = [];
    this.redoStack = [];
    this.preview = null;
    this.status = "";
    this.render();
    this.queuePreview();
  }
  createSensorTemplate() {
    const element = this.element;
    const state = this.hass.states[element.entity_id];
    const type = "output:" + this.outputType(state);
    const sample = element.entity_id;
    const source =
      this.templates[element.template === "auto" ? type : element.template];
    const initial = clone(source?.document || this.defaultTemplate());
    if (!source && /^output:(binary|weather)/.test(type))
      initial.elements = initial.elements.filter(
        (el) => el.text !== "{{state}} {{unit}}",
      );
    this.switchMode("template");
    const key = type + ":custom:" + createId();
    this.templateDrafts.set(key, {
      width: source?.width || 140,
      height: source?.height || 60,
      name: this.entityName(state) + " style",
      sensor_type: type,
      document: initial,
      dirty: true,
    });
    this.loadTemplate(key);
    this.sampleEntity = sample;
    this.createdForElement = element.id;
    this.render();
    this.queuePreview();
  }
  previewRequest() {
    if (this.mode === "template")
      return this.api("preview_template", {
        template: {
          width: this.tag.width,
          height: this.tag.height,
          name: this.templateName,
          sensor_type: this.templateSensorType,
          document: clone(this.document),
        },
        entity_id: this.sampleEntity,
      });
    return this.api("preview", {
      entry_id: this.tag.entry_id,
      document: clone(this.document),
    });
  }
  tokenText(text) {
    if (this.mode !== "template") return text;
    const state = this.sampleState();
    const values = {
      name: state ? this.entityName(state) : "Name",
      state: state?.state || "State",
      unit: state?.attributes.unit_of_measurement || "",
      icon: state?.attributes.icon || this.defaultIcon(state),
    };
    return text.replace(/{{(name|state|unit|icon)}}/g, (_, key) => values[key]);
  }
  defaultIcon(state) {
    if (!state) return "mdi:eye";
    if (state.attributes.icon) return state.attributes.icon;
    const active = state.state === "on",
      dc = state.attributes.device_class;
    if (state.entity_id.startsWith("weather."))
      return (
        "mdi:" +
        ({
          sunny: "weather-sunny",
          "clear-night": "weather-night",
          partlycloudy: "weather-partly-cloudy",
          cloudy: "weather-cloudy",
          rainy: "weather-rainy",
          pouring: "weather-pouring",
          snowy: "weather-snowy",
          "snowy-rainy": "weather-snowy-rainy",
          fog: "weather-fog",
          windy: "weather-windy",
          "windy-variant": "weather-windy-variant",
          lightning: "weather-lightning",
          "lightning-rainy": "weather-lightning-rainy",
          hail: "weather-hail",
          exceptional: "alert-circle",
        }[state.state] || "weather-cloudy")
      );
    if (state.entity_id.startsWith("binary_sensor.")) {
      const pairs = {
        window: ["window-closed", "window-open"],
        door: ["door-closed", "door-open"],
        motion: ["motion-sensor-off", "motion-sensor"],
        plug: ["power-plug-off", "power-plug"],
        power: ["flash-off", "flash"],
        lock: ["lock", "lock-open"],
      };
      return (
        "mdi:" +
        (pairs[dc] || ["radiobox-blank", "checkbox-marked-circle"])[
          Number(active)
        ]
      );
    }
    return (
      "mdi:" +
      ({
        temperature: "thermometer",
        humidity: "water-percent",
        battery: "battery",
        power: "flash",
        energy: "lightning-bolt",
        timestamp: "calendar-clock",
      }[dc] || "eye")
    );
  }
  iconGlyph(name, size = 24) {
    return `<span class="mdi" aria-hidden="true" style="font-size:${size}px">${esc(this.icons[name] || "")}</span>`;
  }
  renderIconChoices(search = "") {
    const grid = this.shadowRoot.querySelector(".icon-picker");
    if (grid)
      grid.innerHTML = Object.keys(this.icons)
        .filter((name) => name.includes(search.toLowerCase()))
        .slice(0, 120)
        .map(
          (name) =>
            `<button data-icon="${name}" aria-label="${name}" title="${name}">${this.iconGlyph(name)}</button>`,
        )
        .join("");
  }
  colorPicker(key, value, label) {
    return `<label>${label}<div class="picker" role="group" aria-label="${label}">${[
      ...palette(this.tag.colors),
      ...(["background", "display-background"].includes(key) &&
      key !== "display-background"
        ? ["transparent"]
        : []),
    ]
      .map(
        (color) =>
          `<button class="swatch" style="--swatch:${color};${color === "transparent" ? "background:repeating-conic-gradient(#ccc 0% 25%,white 0% 50%) 50%/8px 8px" : ""}" data-pick="${key}" data-value="${color}" aria-label="${label}: ${color}" title="${color}" aria-pressed="${value === color}"></button>`,
      )
      .join("")}</div></label>`;
  }
  panelMenu(action, open, label, id) {
    return `<button class="icon-button" data-action="${action}" aria-label="Toggle ${label} panel" aria-controls="${id}" title="${open ? "Hide" : "Show"} ${label}" aria-expanded="${open}">${icon("menu")}</button>`;
  }
  render() {
    this.finishTextEdit();
    const tag = this.tag,
      element = this.element;
    this.shadowRoot.innerHTML = `<style>${style} [hidden]{display:none!important}</style><header><ha-menu-button></ha-menu-button><h1>Label designer</h1><span>Live Home Assistant data on e-paper</span><nav class="tabs" aria-label="Designer mode"><button data-action="display-mode" aria-pressed="${this.mode === "display"}">Display</button><button data-action="template-mode" aria-pressed="${this.mode === "template"}">Sensor templates</button></nav></header>${this.templateControls()}<div class="toolbar"><select id="tag" aria-label="Tag" ${this.mode === "template" ? "hidden" : ""}>${this.tags.map((item) => `<option value="${esc(item.entry_id)}" ${item === tag ? "selected" : ""}>${esc(item.title)} · ${item.width}×${item.height}</option>`).join("")}</select><button data-action="reload" ${this.mode === "template" ? "hidden" : ""} class="icon-button" aria-label="Refresh tags" title="Refresh tags">${toolIcon("reload")}</button><button data-action="save" ${!tag || this.busy ? "disabled" : ""} class="icon-button" aria-label="Save" title="Save">${toolIcon("save")}${this.dirty ? "·" : ""}</button><button class="primary icon-button" aria-label="Send to tag" title="Send to tag" data-action="send" ${this.mode === "template" ? "hidden" : ""} ${this.mode === "template" || !tag?.writable || this.busy ? "disabled" : ""}>${toolIcon("send")}</button><label class="check" ${this.mode === "template" ? "hidden" : ""}><input id="auto" type="checkbox" ${this.document.auto_update ? "checked" : ""} ${!tag?.writable ? "disabled" : ""}>Auto update sensor</label>${this.document.auto_update && this.mode === "display" ? `<label title="Minimum update interval">↻ <input id="interval" aria-label="Update interval" type="number" min="10" max="86400" value="${this.document.interval}" style="width:75px"> s</label>` : ""}<button data-action="undo" ${!this.undoStack.length ? "disabled" : ""} class="icon-button" aria-label="Undo" title="Undo (⌘/Ctrl Z)">${toolIcon("undo")}</button><button data-action="redo" ${!this.redoStack.length ? "disabled" : ""} class="icon-button" aria-label="Redo" title="Redo (⌘/Ctrl Shift Z)">${toolIcon("redo")}</button><button data-action="zoom-out" aria-label="Zoom out">−</button><label><select id="zoom" aria-label="Preview zoom"><option value="fit" ${this.zoomMode === "fit" ? "selected" : ""}>Fit</option>${[
      ...new Set([
        0.25,
        0.5,
        0.75,
        1,
        1.5,
        2,
        3,
        4,
        6,
        8,
        ...(this.zoomMode === "manual" ? [this.zoom] : []),
      ]),
    ]
      .sort((a, b) => a - b)
      .map(
        (value) =>
          `<option value="${value}" ${this.zoomMode === "manual" && value === this.zoom ? "selected" : ""}>${Math.round(value * 100)}%</option>`,
      )
      .join(
        "",
      )}</select></label><button data-action="zoom-in" aria-label="Zoom in">+</button><button data-action="fit" aria-label="Fit preview">Fit</button></div><div class="status" role="status"></div>${
      tag
        ? `<div class="workspace ${this.libraryOpen ? "" : "library-closed"} ${this.inspectorOpen ? "" : "inspector-closed"}"><section id="library" class="library card"><div class="panel-heading"><h2>${this.mode === "template" ? "Template parts" : "Entities"}</h2>${this.panelMenu("toggle-library", this.libraryOpen, "entities", "library")}</div>${this.templateParts()}<div ${this.mode === "template" ? "hidden" : ""}><ha-entity-picker id="entity-picker"></ha-entity-picker><div class="entity-preview"></div></div><h2>Add an element</h2><div class="tools"><button class="icon-button" data-add="text" aria-label="Add text" title="Text">${toolIcon("text")}</button><button class="icon-button" data-add="rectangle" aria-label="Add shape" title="Shape">${toolIcon("shape")}</button><button class="icon-button" data-add="icon" aria-label="Add icon" title="Icon">${toolIcon("icon")}</button><button class="icon-button" data-add="image" aria-label="Add image" title="Image">${toolIcon("image")}</button></div><div class="footer-tools"><button data-action="export">Export JSON</button><button data-action="import">Import JSON</button><input id="file" type="file" accept="application/json" hidden></div></section><section class="card preview-card"><div class="panel-heading">${!this.libraryOpen ? this.panelMenu("toggle-library", false, "entities", "library") : ""}<h2>${tag.width} × ${tag.height} · ${esc(tag.colors)} <span class="muted">${this.preview ? "Exact rendered preview" : "Editing preview"}</span></h2>${!this.inspectorOpen ? this.panelMenu("toggle-inspector", false, "properties", "inspector") : ""}</div><div class="canvas-wrap"><div class="stage-space" style="width:${tag.width * this.zoom}px;height:${tag.height * this.zoom}px"><div class="stage" style="width:${tag.width}px;height:${tag.height}px;transform:scale(${this.zoom});background:${this.document.background}" tabindex="0" role="group" aria-label="Display canvas"></div></div></div><p class="muted">Arrow keys move 1 px · Shift + arrows move 10 px · Delete / Backspace removes · Right-click for actions · ⌘/Ctrl + D duplicates · ⌘/Ctrl + Z undoes</p></section><aside id="inspector" class="inspector side-column"><section class="card"><div class="panel-heading"><h2>${element ? "Element properties" : "Select an element"}</h2>${this.panelMenu("toggle-inspector", this.inspectorOpen, "properties", "inspector")}</div><div class="props">${this.properties(element)}</div></section><section class="card layer-card"><h2>Layers</h2><div class="layers">${[
            ...this.document.elements,
          ]
            .reverse()
            .map(
              (item) =>
                `<button class="layer ${item.id === this.selected ? "active" : ""}" data-select="${esc(item.id)}">${esc(item.label || item.entity_id || item.text || item.type)}</button>`,
            )
            .join(
              "",
            )}</div>${this.colorPicker("display-background", this.document.background, "Display background")}</section></aside></div>`
        : ""
    }`;
    this.renderEntities();
    this.drawStage();
    this.renderStatus();
    this.resizeObserver.disconnect();
    const previewWindow = this.shadowRoot.querySelector(".canvas-wrap");
    if (previewWindow) {
      this.resizeObserver.observe(previewWindow);
      this.fitPreview();
    }
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this.hass;
      menu.narrow = this.narrow;
    }
    if (this.busy) {
      this.shadowRoot.querySelector(".workspace")?.setAttribute("inert", "");
      this.shadowRoot
        .querySelectorAll("button")
        .forEach((button) => (button.disabled = true));
    }
  }
  fitPreview() {
    if (this.zoomMode !== "fit" || !this.tag) return;
    const previewWindow = this.shadowRoot.querySelector(".canvas-wrap");
    if (!previewWindow) return;
    this.zoom = Math.max(
      0.1,
      Math.min(
        8,
        Math.floor(
          Math.min(
            (previewWindow.clientWidth - 60) / this.tag.width,
            (previewWindow.clientHeight - 60) / this.tag.height,
          ) * 100,
        ) / 100,
      ),
    );
    const stage = this.shadowRoot.querySelector(".stage"),
      space = this.shadowRoot.querySelector(".stage-space");
    stage.style.transform = `scale(${this.zoom})`;
    space.style.width = `${this.tag.width * this.zoom}px`;
    space.style.height = `${this.tag.height * this.zoom}px`;
    const trash = this.shadowRoot.querySelector(".delete-handle");
    if (trash) trash.style.transform = `scale(${1 / this.zoom})`;
    const option = this.shadowRoot.querySelector('#zoom option[value="fit"]');
    if (option) option.textContent = `Fit (${Math.round(this.zoom * 100)}%)`;
  }
  stateIconRows(element) {
    const sample = this.sampleState();
    const states = [
      ...new Set([
        ...(this.outputType(sample) === "binary"
          ? ["on", "off"]
          : sample
            ? [sample.state]
            : []),
        ...Object.keys(element.state_icons || {}),
      ]),
    ];
    return `<div class="wide"><strong>State → icon</strong>${states
      .map((state) => {
        const name = element.state_icons?.[state] || "{{icon}}";
        const stateObj = sample && { ...sample, state };
        return `<div style="display:flex;gap:8px;align-items:center;margin-top:6px"><span style="min-width:48px">${esc(state)}</span><span>→</span><button class="icon-choice" data-action="pick-icon" data-icon-state="${esc(state)}" aria-label="Choose icon for ${esc(state)}">${this.iconGlyph(name === "{{icon}}" ? this.defaultIcon(stateObj) : name)}<span>${name === "{{icon}}" ? "HA state icon" : esc(name.replace("mdi:", ""))}</span></button></div>`;
      })
      .join(
        "",
      )}<div style="display:flex;gap:6px;margin-top:8px"><input id="new-icon-state" aria-label="New icon state" placeholder="Another state"><button data-action="add-icon-state" aria-label="Add state mapping">+</button></div></div>`;
  }
  properties(element) {
    if (!element)
      return '<p class="muted wide">Click a block to move, resize, or bind it to an entity.</p>';
    const field = (key, label, type = "text", wide = false) =>
      `<label class="${wide ? "wide" : ""}">${label}<input data-property="${key}" type="${type}" value="${esc(element[key] ?? "")}" ${type === "number" ? 'step="1"' : ""}></label>`;
    let html = ["x", "y", "width", "height"]
      .map((key) => field(key, key[0].toUpperCase() + key.slice(1), "number"))
      .join("");
    if (["sensor", "text"].includes(element.type))
      html +=
        field("font_size", "Font size", "number") +
        `<label>Align<div class="picker" role="group" aria-label="Text alignment">${["left", "center", "right"].map((value) => `<button class="align-button" data-pick="align" data-value="${value}" aria-label="Align ${value}" title="Align ${value}" aria-pressed="${element.align === value}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 4h18M${value === "right" ? 9 : value === "center" ? 6 : 3} 9h12M3 14h18M${value === "right" ? 9 : value === "center" ? 6 : 3} 19h12"/></svg></button>`).join("")}</div></label>`;
    html += this.colorPicker("color", element.color, "Colour");
    if (shapeTypes.includes(element.type))
      html += `<label class="wide">Shape<select data-property="type" aria-label="Shape">${shapeTypes.map((type) => `<option value="${type}" ${element.type === type ? "selected" : ""}>${type.replace("_", " ")}</option>`).join("")}</select></label>`;
    if (["sensor", "text"].includes(element.type))
      html += this.colorPicker("background", element.background, "Background");
    if (element.type === "image")
      html += `<label class="wide">Image<input id="image-file" aria-label="Upload image" type="file" accept="image/*"></label><label class="wide">Fit<select data-property="image_fit" aria-label="Image fit">${["contain", "fill", "stretch"].map((value) => `<option value="${value}" ${element.image_fit === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>`;
    if (element.type === "icon")
      html += `<label class="wide">Icon<button class="icon-choice" data-action="pick-icon" aria-label="Choose icon">${this.iconGlyph(this.tokenText(element.icon), 24)}<span>${element.icon === "{{icon}}" ? "HA state icon" : esc(element.icon.replace("mdi:", ""))}</span></button><div class="icon-popover" hidden><input id="icon-search" type="search" aria-label="Search icons" placeholder="Search icons"><button data-icon="{{icon}}">HA state icon</button><div class="icon-picker"></div></div><input data-property="icon" aria-label="Icon name" value="${esc(element.icon)}" hidden></label>`;

    if (this.mode === "template" && element.type === "icon")
      html += this.stateIconRows(element);
    if (this.mode === "template" && element.type !== "icon")
      html += `<label class="wide">Show for state<input data-property="state" aria-label="Visible state" placeholder="All states" list="template-states" value="${esc(element.state || "")}"><datalist id="template-states">${[
        ...new Set([
          "on",
          "off",
          ...(this.templateKey.startsWith("weather:")
            ? [
                "sunny",
                "cloudy",
                "partlycloudy",
                "rainy",
                "pouring",
                "snowy",
                "snowy-rainy",
                "clear-night",
                "fog",
                "windy",
                "hail",
                "lightning",
                "lightning-rainy",
              ]
            : []),
          ...this.entities()
            .filter(
              (state) => this.sensorType(state) === this.templateSensorType,
            )
            .map((state) => state.state),
        ]),
      ]
        .map((state) => `<option value="${esc(state)}"></option>`)
        .join("")}</datalist></label>`;
    if (element.type === "text")
      html += `<label class="wide">Text<textarea data-property="text" rows="3">${esc(element.text)}</textarea></label>`;
    if (element.type === "sensor") {
      if (element.entity_id.startsWith("weather."))
        html += `<label>When<select data-property="weather_when" aria-label="Weather time">${[
          ["now", "Now"],
          ["later_today", "Later today"],
          ["tomorrow", "Tomorrow"],
          ["in_2_days", "In 2 days"],
          ["in_3_days", "In 3 days"],
        ]
          .map(
            ([key, label]) =>
              `<option value="${key}" ${(element.weather_when || "now") === key ? "selected" : ""}>${label}</option>`,
          )
          .join(
            "",
          )}</select></label><label>Show<select data-property="weather_field" aria-label="Weather value">${[
          ["condition", "Condition"],
          ["temperature", "Temperature"],
          ["templow", "Low temperature"],
          ["precipitation", "Rain / snow"],
          ["precipitation_probability", "Rain chance"],
          ["wind_speed", "Wind speed"],
          ["humidity", "Humidity"],
        ]
          .map(
            ([key, label]) =>
              `<option value="${key}" ${(element.weather_field || "condition") === key ? "selected" : ""}>${label}</option>`,
          )
          .join("")}</select></label>`;
      html += `<label class="wide">Template<select data-property="template" aria-label="Sensor template"><option value="auto">By sensor type</option><option value="default" ${element.template === "default" ? "selected" : ""}>HA tile</option>${Object.keys(
        this.templates,
      )
        .filter(
          (key) =>
            this.templateCompatibility(this.templates[key], key) ===
            this.outputType(this.hass.states[element.entity_id]),
        )
        .map(
          (key) =>
            `<option value="${esc(key)}" ${element.template === key ? "selected" : ""}>${esc(this.templates[key]?.name || this.templateDrafts.get(key)?.name || (key.startsWith("output:") ? key.split(":")[1] + " template" : key.replace(":", " · ")))}</option>`,
        )
        .join(
          "",
        )}<option value="__new__">＋ Create template…</option></select></label>`;
      html += `<label class="wide">Entity<select data-property="entity_id" aria-label="Bound entity">${this.entities()
        .map(
          (state) =>
            `<option value="${esc(state.entity_id)}" ${state.entity_id === element.entity_id ? "selected" : ""}>${esc(this.entityName(state))}</option>`,
        )
        .join("")}</select></label>`;
      html += `<label class="wide check"><input type="checkbox" data-property="show_label" ${element.show_label ? "checked" : ""}>Show label</label>`;
      if (element.show_label)
        html += field("label", "Label override", "text", true);
      const state = this.hass.states[element.entity_id];
      const numeric =
        state &&
        !state.entity_id.startsWith("binary_sensor.") &&
        (state.entity_id.startsWith("weather.")
          ? element.weather_field && element.weather_field !== "condition"
          : state.state.trim() !== "" && Number.isFinite(Number(state.state)));
      if (numeric) {
        html += `<label class="wide check"><input type="checkbox" data-property="show_unit" ${element.show_unit ? "checked" : ""}>Show unit</label>`;
        if (element.show_unit)
          html += field(
            "decimals",
            "Decimals (auto when blank)",
            "number",
            true,
          );
      }
    }
    return html;
  }
  renderEntities() {
    const picker = this.shadowRoot.querySelector("#entity-picker");
    if (!picker) return;
    picker.hass = this.hass;
    picker.includeDomains = [
      "sensor",
      "binary_sensor",
      "weather",
      "input_number",
      "number",
      "input_boolean",
      "input_select",
      "select",
      "counter",
    ];
    picker.label = "Sensor";
    picker.searchLabel = "Search sensors";
    picker.allowCustomEntity = false;
    picker.value = this.libraryEntity;
    picker.addEventListener("value-changed", (event) => {
      const id = event.detail.value;
      if (!id) {
        this.libraryEntity = "";
        this.renderEntityPreview();
        return;
      }
      this.libraryEntity = id;
      this.add("sensor", this.hass.states[id]);
    });
    this.renderEntityPreview();
  }
  renderEntityPreview() {
    const node = this.shadowRoot.querySelector(".entity-preview");
    const state = this.hass?.states[this.libraryEntity];
    if (!node) return;
    node.innerHTML = state
      ? `<div class="entity-state" data-entity="${esc(state.entity_id)}" draggable="true"><ha-state-icon></ha-state-icon><div class="state-copy"><div class="state-name">${esc(this.entityName(state))}</div><div class="state-value">${esc(this.hass.formatEntityState?.(state) || state.state)}</div></div><button class="icon-button" data-action="add-current-entity" aria-label="Add selected sensor" title="Add selected sensor">+</button></div>`
      : "";
    const icon = node.querySelector("ha-state-icon");
    if (icon) {
      icon.hass = this.hass;
      icon.stateObj = state;
    }
  }
  filteredEntities() {
    return this.entities().filter((state) =>
      (state.entity_id + " " + this.entityName(state))
        .toLowerCase()
        .includes(this.search.toLowerCase()),
    );
  }
  sensorContent(element, state, label) {
    let key = element.template || "auto";
    if (key === "auto" && state) {
      key = this.sensorType(state);
      if (!this.templates[key])
        key = state.entity_id.split(".")[0] + ":default";
    }
    const template = this.templates[key];
    if (template && state) {
      const values = {
        name: label,
        state:
          element.decimals === undefined ||
          ["unknown", "unavailable"].includes(state.state)
            ? state.state
            : Number(state.state).toFixed(element.decimals),
        unit: element.show_unit
          ? state.attributes.unit_of_measurement || ""
          : "",
        icon: this.defaultIcon(state),
      };
      const text = (value) =>
        String(value).replace(
          /{{(name|state|unit|icon)}}/g,
          (_, name) => values[name],
        );
      return template.document.elements
        .filter((child) => !child.state || child.state === state.state)
        .map((child) => {
          const sx = element.width / template.width,
            sy = element.height / template.height;
          const content =
            child.type === "text"
              ? esc(text(child.text)).replace(/\n/g, "<br>")
              : child.type === "icon"
                ? this.iconGlyph(
                    text(child.icon),
                    Math.min(child.width * sx, child.height * sy),
                  )
                : "";
          return `<div style="position:absolute;left:${child.x * sx}px;top:${child.y * sy}px;width:${child.width * sx}px;height:${child.height * sy}px;overflow:hidden;color:${child.color};background:${["rectangle", "line"].includes(child.type) ? child.color : child.background};font-size:${child.font_size * Math.min(sx, sy)}px;text-align:${child.align}">${content}</div>`;
        })
        .join("");
    }
    const weatherNumber =
      state?.entity_id.startsWith("weather.") &&
      element.weather_field &&
      element.weather_field !== "condition";
    const visual =
      state?.entity_id.startsWith("binary_sensor.") ||
      (state?.entity_id.startsWith("weather.") && !weatherNumber);
    const value = weatherNumber
      ? String(state.attributes[element.weather_field] ?? "") +
        (element.show_unit && state.attributes[element.weather_field + "_unit"]
          ? " " + state.attributes[element.weather_field + "_unit"]
          : "")
      : this.value(element);
    const icon = weatherNumber
      ? this.defaultIcon({
          entity_id: "sensor.weather",
          state: value,
          attributes: { device_class: element.weather_field },
        })
      : this.defaultIcon(state);
    return `<div class="tile-icon">${this.iconGlyph(icon, 32)}</div><div class="tile-copy">${element.show_label ? `<div class="label">${esc(label)}</div>` : ""}<div class="value">${visual ? "" : esc(value)}</div></div>`;
  }
  drawStage() {
    const stage = this.shadowRoot.querySelector(".stage");
    if (!stage || this.editingTextId) return;
    const focusedId = this.shadowRoot.activeElement?.dataset.id;
    stage.classList.toggle("exact-mode", !!this.preview);
    stage.innerHTML =
      (this.preview
        ? `<img class="exact" src="${this.preview}" alt="Exact rendered display">`
        : "") +
      this.document.elements
        .map((element, index) => {
          const state = this.hass?.states[element.entity_id];
          const label =
            element.label ||
            (state ? this.entityName(state) : element.entity_id);
          let content = "";
          if (element.type === "sensor")
            content = this.sensorContent(element, state, label);
          if (element.type === "image" && element.image)
            content = `<img src="${esc(element.image)}" alt="" style="width:100%;height:100%;object-fit:${element.image_fit === "stretch" ? "fill" : element.image_fit === "fill" ? "cover" : "contain"}">`;
          if (element.type === "text")
            content = esc(this.tokenText(element.text)).replace(/\n/g, "<br>");
          if (element.type === "icon")
            content = this.iconGlyph(
              this.tokenText(
                element.state_icons?.[this.sampleState()?.state] ||
                  element.icon,
              ),
              Math.min(element.width, element.height),
            );
          if (shapeTypes.includes(element.type)) {
            const shape =
              element.type === "triangle"
                ? '<polygon points="50,0 100,100 0,100"/>'
                : element.type === "ellipse"
                  ? '<ellipse cx="50" cy="50" rx="50" ry="50"/>'
                  : `<rect width="100" height="100" rx="${element.type === "rounded_rectangle" ? 15 : 0}"/>`;
            content = `<svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" fill="currentColor" aria-hidden="true">${shape}</svg>`;
          }
          const rendered = this.layerPreviews[element.id];
          return `<div class="el ${rendered ? "rendered" : ""} ${element.id === this.selected ? "selected" : ""}" data-id="${esc(element.id)}" role="button" tabindex="0" aria-label="${esc(label || element.text || element.type)}" style="left:${element.x}px;top:${element.y}px;width:${element.width}px;height:${element.height}px;color:${element.color};background:${element.background};font-size:${element.font_size}px;text-align:${element.align};z-index:${index + 1}">${rendered ? `<img class="layer-preview" src="${rendered}" alt="" aria-hidden="true">` : ""}<div class="content" ${this.mode === "template" && element.state && element.state !== this.sampleState()?.state ? 'style="opacity:.2"' : ""}>${content}</div>${element.id === this.selected ? `<span class="handle" aria-label="Resize element"></span><button class="delete-handle" data-action="delete" aria-label="Delete selected element" title="Delete (Delete / Backspace)" style="transform:scale(${1 / this.zoom});transform-origin:bottom right">${icon("delete")}</button>` : ""}</div>`;
        })
        .join("");
    if (focusedId) this.focusElement();
    stage.querySelectorAll("ha-state-icon").forEach((icon) => {
      const element = this.document.elements.find(
        (el) => el.id === icon.closest("[data-id]").dataset.id,
      );
      icon.hass = this.hass;
      icon.stateObj = this.hass.states[element.entity_id];
    });
  }
  add(type, entity, x, y) {
    this.checkpoint();
    const element = newElement(type, this.tag, entity);
    if (x !== undefined) {
      element.x = x;
      element.y = y;
      clampBox(element, this.tag);
    }
    this.document.elements.push(element);
    this.selected = element.id;
    this.edited();
    this.focusElement();
  }
  focusElement() {
    this.shadowRoot
      .querySelector(this.selected ? `[data-id="${this.selected}"]` : ".stage")
      ?.focus({ preventScroll: true });
  }
  async click(event) {
    const button = event.target.closest("button");
    if (!button || this.busy) return;
    this.closeContextMenu();
    if (["display-mode", "template-mode"].includes(button.dataset.action)) {
      this.switchMode(
        button.dataset.action === "template-mode" ? "template" : "display",
      );
      return;
    }
    if (button.dataset.action === "add-current-entity") {
      this.add("sensor", this.hass.states[this.libraryEntity]);
      return;
    }
    if (button.dataset.action === "add-icon-state") {
      const state = this.shadowRoot
        .querySelector("#new-icon-state")
        .value.trim();
      if (!state) return;
      this.checkpoint();
      this.element.state_icons ||= {};
      this.element.state_icons[state] = "{{icon}}";
      this.edited();
      return;
    }
    if (button.dataset.action === "pick-icon") {
      this.iconMappingState = button.dataset.iconState;
      const popover = this.shadowRoot.querySelector(".icon-popover");
      popover.hidden = false;
      this.renderIconChoices();
      popover.querySelector("input").focus();
      return;
    }
    if (button.dataset.icon) {
      this.checkpoint();
      if (this.iconMappingState !== undefined) {
        this.element.state_icons ||= {};
        this.element.state_icons[this.iconMappingState] = button.dataset.icon;
        this.element.state = "";
      } else this.element.icon = button.dataset.icon;
      this.edited();
      return;
    }
    if (button.dataset.action === "add-state-icon") {
      this.add("icon");
      this.element.icon = "{{icon}}";
      this.edited();
      return;
    }
    if (button.dataset.pick) {
      this.checkpoint();
      if (button.dataset.pick === "display-background")
        this.document.background = button.dataset.value;
      else if (this.element)
        this.element[button.dataset.pick] = button.dataset.value;
      this.edited();
      return;
    }
    if (button.dataset.token) {
      this.add("text");
      this.element.text = `{{${button.dataset.token}}}`;
      this.edited();
      this.focusElement();
      return;
    }
    if (
      ["duplicate", "delete", "back", "front", "center"].includes(
        button.dataset.action,
      )
    ) {
      this.transform(button.dataset.action);
      return;
    }
    if (
      ["toggle-library", "toggle-inspector"].includes(button.dataset.action)
    ) {
      if (button.dataset.action === "toggle-library")
        this.libraryOpen = !this.libraryOpen;
      else this.inspectorOpen = !this.inspectorOpen;
      this.render();
      return;
    }
    if (["zoom-in", "zoom-out", "fit"].includes(button.dataset.action)) {
      if (button.dataset.action === "fit") this.zoomMode = "fit";
      else {
        this.zoomMode = "manual";
        this.zoom = Math.max(
          0.1,
          Math.min(
            8,
            Math.round(
              this.zoom *
                (button.dataset.action === "zoom-in" ? 1.25 : 0.8) *
                100,
            ) / 100,
          ),
        );
      }
      this.render();
      return;
    }
    if (button.dataset.entity) {
      this.add("sensor", this.hass.states[button.dataset.entity]);
      return;
    }
    if (button.dataset.add) {
      this.add(button.dataset.add);
      return;
    }
    if (button.dataset.select) {
      this.selected = button.dataset.select;
      this.render();
      this.focusElement();
      return;
    }
    const action = button.dataset.action;
    try {
      if (["save", "preview", "send"].includes(action)) {
        this.busy = true;
        this.error = false;
        this.status = action === "send" ? "Sending display…" : "Working…";
        this.render();
        const result =
          this.mode === "template"
            ? action === "save"
              ? await this.api("save_template", {
                  key: this.templateKey,
                  template: {
                    width: this.tag.width,
                    height: this.tag.height,
                    name: this.templateName,
                    sensor_type: this.templateSensorType,
                    document: this.document,
                  },
                })
              : await this.previewRequest()
            : await this.api(action, {
                entry_id: this.tag.entry_id,
                document: this.document,
              });
        if (action === "save") {
          this.document = this.mode === "template" ? result.document : result;
          if (this.mode === "template")
            this.templates[this.templateKey] = clone(result);
          this.tag.document = clone(this.document);
          this.drafts.delete(this.tag.entry_id);
          this.dirty = false;
          if (this.mode === "template" && this.createdForElement) {
            const session = this.displaySession;
            session.undo.push(clone(session.document));
            session.redo = [];
            session.document.elements.find(
              (el) => el.id === this.createdForElement,
            ).template = this.templateKey;
            session.dirty = true;
            this.createdForElement = null;
          }
          this.status =
            this.mode === "template" ? "Template saved" : "Display saved";
        }
        if (action === "preview") {
          this.preview = result.png;
          this.layerPreviews = result.layers;
          this.status = "Exact rendered preview";
        }
        if (action === "send") {
          this.status =
            result.status === "written"
              ? "Display sent and acknowledged"
              : result.status;
        }
      } else if (action === "reload") {
        this.started = false;
        await this.boot();
        return;
      } else if (action === "undo" || action === "redo") {
        const source = action === "undo" ? this.undoStack : this.redoStack,
          target = action === "undo" ? this.redoStack : this.undoStack;
        if (source.length) {
          target.push(clone(this.document));
          this.document = source.pop();
          this.selected = null;
          this.edited();
        }
      } else if (action === "export") {
        const blob = new Blob([JSON.stringify(this.document, null, 2)], {
            type: "application/json",
          }),
          url = URL.createObjectURL(blob),
          link = document.createElement("a");
        link.href = url;
        link.download = "label-display.json";
        link.click();
        URL.revokeObjectURL(url);
      } else if (action === "import")
        this.shadowRoot.querySelector("#file").click();
      else this.transform(action);
    } catch (error) {
      this.report(error);
    } finally {
      this.busy = false;
      this.render();
    }
  }
  transform(action) {
    const element = this.element;
    if (!element) return;
    if (!["duplicate", "delete", "back", "front", "center"].includes(action))
      return;
    this.checkpoint();
    const elements = this.document.elements,
      index = elements.indexOf(element);
    if (action === "duplicate") {
      const copy = clone(element);
      copy.id = createId();
      copy.x += 8;
      copy.y += 8;
      clampBox(copy, this.tag);
      elements.push(copy);
      this.selected = copy.id;
    }
    if (action === "delete") {
      elements.splice(index, 1);
      this.selected = null;
    }
    if (action === "back") {
      elements.splice(index, 1);
      elements.unshift(element);
    }
    if (action === "front") {
      elements.splice(index, 1);
      elements.push(element);
    }
    if (action === "center")
      element.x = Math.round((this.tag.width - element.width) / 2);
    this.edited();
    this.focusElement();
  }
  closeContextMenu() {
    this.shadowRoot.querySelector(".context-menu")?.remove();
  }
  contextMenu(event) {
    if (event.target.isContentEditable) return;
    const node = event.target.closest("[data-id], [data-select]");
    if (!node || this.busy) return;
    event.preventDefault();
    this.selected = node.dataset.id || node.dataset.select;
    this.render();
    const menu = document.createElement("div");
    menu.className = "context-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", "Element actions");
    menu.style.left = `${Math.min(event.clientX, window.innerWidth - 228)}px`;
    menu.style.top = `${Math.min(event.clientY, window.innerHeight - 220)}px`;
    menu.innerHTML = [
      ["duplicate", "Duplicate", "⌘/Ctrl D"],
      ["delete", "Delete", "⌫"],
      ["back", "Send back", ""],
      ["front", "Bring front", ""],
      ["center", "Center horizontally", ""],
    ]
      .map(
        ([action, label, key]) =>
          `<button role="menuitem" data-action="${action}">${action === "delete" ? icon("delete") : toolIcon(action)}<span>${label}</span><kbd>${key}</kbd></button>`,
      )
      .join("");
    this.shadowRoot.append(menu);
    menu.querySelector("button").focus();
  }
  beginTextEdit() {
    if (this.element?.type !== "text") return;
    clearTimeout(this.previewTimer);
    this.previewSequence++;
    this.preview = null;
    this.shadowRoot.querySelector(".stage").classList.remove("exact-mode");
    const node = this.shadowRoot.querySelector(`[data-id="${this.selected}"]`);
    node.classList.add("editing");
    const content = node.querySelector(".content");
    content.textContent = this.element.text;
    content.contentEditable = "plaintext-only";
    content.dataset.editText = this.selected;
    content.setAttribute("role", "textbox");
    content.setAttribute("aria-label", "Edit display text");
    this.editingTextId = this.selected;
    content.focus();
    const range = document.createRange();
    range.selectNodeContents(content);
    if (this.element.text !== "Your text") range.collapse(false);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }
  finishTextEdit() {
    if (!this.editingTextId) return;
    this.editingTextId = null;
    this.typingProperty = null;
    this.drawStage();
    this.queuePreview();
  }
  input(event) {
    const input = event.target;
    if (input.dataset.editText) {
      if (this.typingProperty !== input) {
        this.checkpoint();
        this.typingProperty = input;
      }
      this.element.text = input.innerText;
      this.dirty = true;
      const field = this.shadowRoot.querySelector('[data-property="text"]');
      if (field) field.value = this.element.text;
      const layer = this.shadowRoot.querySelector(
        `[data-select="${this.selected}"]`,
      );
      if (layer) layer.textContent = this.element.text;
      const save = this.shadowRoot.querySelector('[data-action="save"]');
      if (save) save.innerHTML = toolIcon("save") + "·";
      return;
    }
    if (input.id === "template-name") {
      this.templateName = input.value;
      this.dirty = true;
      return;
    }
    if (["template-width", "template-height"].includes(input.id)) {
      if (!input.validity.valid || !input.value) return;
      this.tag[input.id === "template-width" ? "width" : "height"] = Number(
        input.value,
      );
      this.document.elements.forEach((el) => clampBox(el, this.tag));
      const stage = this.shadowRoot.querySelector(".stage");
      stage.style.width = `${this.tag.width}px`;
      stage.style.height = `${this.tag.height}px`;
      this.edited(false);
      this.fitPreview();
      return;
    }
    if (input.id === "icon-search") {
      this.renderIconChoices(input.value);
      return;
    }
    if (input.id === "search") {
      this.search = input.value;
      this.renderEntities();
    } else if (
      input.dataset.property &&
      this.element &&
      ["text", "textarea", "number"].includes(input.type)
    ) {
      if (input.type === "number" && !input.validity.valid) return;
      if (this.typingProperty !== input) {
        this.checkpoint();
        this.typingProperty = input;
      }
      this.updateProperty(input);
      this.edited(false);
      const save = this.shadowRoot.querySelector('[data-action="save"]');
      if (save) save.innerHTML = toolIcon("save") + "·";
      const layer = this.shadowRoot.querySelector(
        `[data-select="${this.selected}"]`,
      );
      if (layer)
        layer.textContent =
          this.element.label ||
          this.element.entity_id ||
          this.element.text ||
          this.element.type;
    }
  }
  updateProperty(input) {
    const key = input.dataset.property;
    if (key === "weather_field" && input.value === "condition")
      delete this.element.decimals;
    if (key === "type") {
      if (input.value === "line") this.element.height = 2;
      else if (this.element.type === "line") this.element.height = 40;
    }
    if (key === "entity_id" && this.element.entity_id !== input.value) {
      const defaults = newElement(
        "sensor",
        this.tag,
        this.hass.states[input.value],
      );
      delete this.element.decimals;
      if (defaults.decimals !== undefined)
        this.element.decimals = defaults.decimals;
      this.element.show_unit = defaults.show_unit;
    }
    if (key === "decimals" && input.value === "") delete this.element[key];
    else
      this.element[key] =
        input.type === "checkbox"
          ? input.checked
          : input.type === "number"
            ? Number(input.value)
            : input.value;
    if (key === "font_size")
      this.element.font_size = Math.max(
        8,
        Math.min(200, this.element.font_size),
      );
    if (key === "decimals" && this.element.decimals !== undefined)
      this.element.decimals = Math.max(0, Math.min(6, this.element.decimals));
    clampBox(this.element, this.tag);
  }
  async change(event) {
    const input = event.target,
      id = input.id;
    if (id === "template-type") {
      this.loadTemplate(input.value);
      return;
    }
    if (id === "template-sample") {
      this.sampleEntity = input.value;
      this.templateSensorType = "output:" + this.outputType(this.sampleState());
      this.dirty = true;
      this.render();
      this.preview = null;
      this.drawStage();
      this.queuePreview();
      return;
    }
    if (["template-width", "template-height"].includes(id)) {
      this.tag[id === "template-width" ? "width" : "height"] = Math.max(
        16,
        Math.min(1000, Number(input.value)),
      );
      this.document.elements.forEach((el) => clampBox(el, this.tag));
      this.edited();
      return;
    }
    if (id === "tag") {
      this.load(this.tags.find((tag) => tag.entry_id === input.value));
      return;
    }
    if (id === "zoom") {
      this.zoomMode = input.value === "fit" ? "fit" : "manual";
      if (this.zoomMode === "manual") this.zoom = Number(input.value);
      this.render();
      return;
    }
    if (id === "image-file") {
      const file = input.files[0];
      if (!file) return;
      const element = this.element;
      const reader = new FileReader();
      reader.onload = () => {
        this.checkpoint();
        element.image = reader.result;
        this.edited();
      };
      reader.readAsDataURL(file);
      return;
    }
    if (id === "file") {
      try {
        const document = JSON.parse(await input.files[0].text());
        await this.api("preview", { entry_id: this.tag.entry_id, document });
        this.checkpoint();
        this.document = document;
        this.selected = null;
        this.edited();
      } catch (error) {
        this.report(error);
      }
      return;
    }
    if (["auto", "interval", "background"].includes(id)) {
      this.checkpoint();
      if (id === "auto") this.document.auto_update = input.checked;
      if (id === "interval")
        this.document.interval = Math.max(
          10,
          Math.min(86400, Number(input.value) || 60),
        );
      if (id === "background") this.document.background = input.value;
      this.edited();
      return;
    }
    if (input.dataset.property === "template" && input.value === "__new__") {
      this.createSensorTemplate();
      return;
    }
    if (input.dataset.property && this.element) {
      if (["text", "textarea", "number"].includes(input.type)) return;
      this.checkpoint();
      this.updateProperty(input);
      this.edited();
    }
  }

  key(event) {
    if (this.busy) return;
    const context = event.target.closest(".context-menu");
    if (context && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      const buttons = [...context.querySelectorAll("button")];
      const index = buttons.indexOf(event.target);
      buttons[
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) %
          buttons.length
      ].focus();
      return;
    }
    if (event.key === "Escape") {
      this.finishTextEdit();
      this.closeContextMenu();
      this.focusElement();
      return;
    }
    if (
      ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName) ||
      event.target.isContentEditable
    )
      return;
    if (event.key === "Enter" && this.element?.type === "text") {
      event.preventDefault();
      this.beginTextEdit();
      return;
    }
    const cmd = event.metaKey || event.ctrlKey,
      key = event.key.toLowerCase();
    if (cmd && ["z", "y", "s", "d"].includes(key)) {
      event.preventDefault();
      if (key === "d") this.transform("duplicate");
      else
        this.shadowRoot
          .querySelector(
            `[data-action="${key === "s" ? "save" : key === "y" || event.shiftKey ? "redo" : "undo"}"]`,
          )
          ?.click();
      return;
    }
    if (key === "delete" || key === "backspace") {
      event.preventDefault();
      this.transform("delete");
      return;
    }
    const directions = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    if (this.element && directions[event.key]) {
      event.preventDefault();
      this.checkpoint();
      const step = event.shiftKey ? 10 : 1,
        [x, y] = directions[event.key];
      this.element.x += x * step;
      this.element.y += y * step;
      clampBox(this.element, this.tag);
      this.edited();
      this.focusElement();
    }
  }
  pointer(event) {
    if (
      event.button !== 0 ||
      event.target.isContentEditable ||
      event.target.closest("button")
    )
      return;
    const node = event.target.closest("[data-id]");
    if (!node) return;
    event.preventDefault();
    this.selected = node.dataset.id;
    const element = this.element,
      start = clone(element),
      resize = !!event.target.closest(".handle"),
      startX = event.clientX,
      startY = event.clientY;
    let moved = false;
    this.preview = null;
    this.previewSequence++;
    clearTimeout(this.previewTimer);
    this.render();
    this.focusElement();
    const controller = new AbortController();
    this.gesture = controller;
    window.addEventListener(
      "pointermove",
      (move) => {
        const dx = Math.round((move.clientX - startX) / this.zoom),
          dy = Math.round((move.clientY - startY) / this.zoom);
        if (
          !moved &&
          Math.hypot(move.clientX - startX, move.clientY - startY) < 3
        )
          return;
        if (!moved) {
          this.checkpoint();
          moved = true;
        }
        if (resize) {
          element.width = start.width + dx;
          element.height = start.height + dy;
        } else {
          element.x = start.x + dx;
          element.y = start.y + dy;
        }
        clampBox(element, this.tag);
        this.drawStage();
      },
      { signal: controller.signal },
    );
    window.addEventListener(
      "pointerup",
      () => {
        controller.abort();
        this.gesture = null;
        if (moved) {
          this.edited();
          this.focusElement();
        } else if (!resize && element.type === "text") this.beginTextEdit();
        else this.queuePreview();
      },
      { once: true, signal: controller.signal },
    );
    window.addEventListener(
      "pointercancel",
      () => {
        controller.abort();
        this.gesture = null;
        this.edited();
      },
      { once: true, signal: controller.signal },
    );
  }
  drop(event) {
    const stage = event.target.closest(".stage");
    if (!stage) return;
    event.preventDefault();
    const entity = this.hass.states[event.dataTransfer.getData("text/plain")];
    if (!entity) return;
    const rect = stage.getBoundingClientRect();
    this.add(
      "sensor",
      entity,
      Math.round((event.clientX - rect.left) / this.zoom),
      Math.round((event.clientY - rect.top) / this.zoom),
    );
  }
  queuePreview() {
    clearTimeout(this.previewTimer);
    if (!this.tag || this.editingTextId) return;
    const sequence = ++this.previewSequence;
    this.previewTimer = setTimeout(async () => {
      if (this.previewInFlight) {
        this.previewQueued = true;
        return;
      }
      this.previewInFlight = true;
      try {
        if (this.mode === "template" && !this.sampleEntity) return;
        const result = await this.previewRequest();
        if (sequence === this.previewSequence && !this.gesture) {
          this.preview = result.png;
          this.layerPreviews = result.layers;
          this.drawStage();
          const title = this.shadowRoot
            .querySelector(".canvas-wrap")
            ?.previousElementSibling?.querySelector("span");
          if (title) title.textContent = "Exact rendered preview";
        }
      } catch (error) {
        if (sequence === this.previewSequence) this.report(error);
      } finally {
        this.previewInFlight = false;
        if (this.previewQueued) {
          this.previewQueued = false;
          this.queuePreview();
        }
      }
    }, 200);
  }
}
customElements.define("ble-esl-designer", BleEslDesigner);
