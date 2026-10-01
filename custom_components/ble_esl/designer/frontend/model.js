export const clone = (value) => JSON.parse(JSON.stringify(value));
// Element IDs need uniqueness within a document. getRandomValues also works
// over plain HTTP, unlike randomUUID, which requires a secure browser context.
export const createId = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
export const palette = (colors) => [
  "black",
  "white",
  ...(colors.includes("R") ? ["red"] : []),
  ...(colors.includes("Y") ? ["yellow"] : []),
];
export const emptyDocument = () => ({
  version: 1,
  background: "white",
  auto_update: false,
  interval: 60,
  elements: [],
});
export function clampBox(element, tag) {
  element.width = Math.max(1, Math.round(element.width));
  element.height = Math.max(1, Math.round(element.height));
  element.x = Math.round(element.x);
  element.y = Math.round(element.y);
  return element;
}
export function newElement(type, tag, entity) {
  const element = {
    id: createId(),
    type,
    x: 8,
    y: 8,
    width: Math.min(140, tag.width - 16),
    height: Math.min(60, tag.height - 16),
    color: "black",
    background: "transparent",
    font_size: 28,
    text: "Your text",
    icon: "mdi:star",
    image: "",
    image_fit: "contain",
    state: "",
    state_icons: {},
    template: "auto",
    weather_when: "now",
    weather_field: "condition",
    entity_id: entity?.entity_id || "",
    label: "",
    show_label: true,
    show_unit: true,
    align: "left",
  };
  if (type === "sensor") {
    const deviceClass = entity?.attributes?.device_class;
    element.font_size = [
      "temperature",
      "humidity",
      "battery",
      "power",
      "energy",
    ].includes(deviceClass)
      ? 32
      : 24;
    if (["temperature", "humidity", "power", "energy"].includes(deviceClass))
      element.decimals = deviceClass === "humidity" ? 0 : 1;
    if (entity?.entity_id?.startsWith("binary_sensor.")) {
      element.font_size = 24;
      element.show_unit = false;
    }
  }
  if (type === "icon") {
    element.width = 32;
    element.height = 32;
  }
  if (type === "line") element.height = 2;
  if (type === "rectangle")
    element.color = palette(tag.colors).includes("red") ? "red" : "black";
  return clampBox(element, tag);
}
