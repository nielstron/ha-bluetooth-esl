import { test, expect } from "@playwright/test";
async function pickSensor(page, id) {
  await page
    .getByRole("combobox", { name: "Search sensors", exact: true })
    .fill(id);
  await page.locator(`ha-entity-picker [data-entity="${id}"]`).click();
}
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => window.panel?.tag);
  await page.evaluate(() => {
    window.panel.document = {
      version: 1,
      elements: [],
      background: "white",
      auto_update: false,
      interval: 60,
    };
    window.panel.render();
  });
});
test("sensor defaults, keyboard, dragging, resize, undo, save and preview", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await pickSensor(page, "sensor.office_temperature");
  await expect(page.locator('[data-property="decimals"]')).toHaveValue("1");
  const element = page.locator(".el.selected");
  await element.focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Shift+ArrowDown");
  await expect(page.locator('[data-property="x"]')).toHaveValue("9");
  await expect(page.locator('[data-property="y"]')).toHaveValue("18");
  await page.keyboard.press("Control+d");
  await expect(page.locator(".el")).toHaveCount(2);
  await page.keyboard.press("Delete");
  await expect(page.locator(".el")).toHaveCount(1);
  await page.getByRole("button", { name: "Undo", exact: false }).click();
  await expect(page.locator(".el")).toHaveCount(2);
  await page.locator(".layer").first().click();
  await expect(page.locator(".el")).toHaveCount(2);
  let box = await page.locator(".el").first().boundingBox();
  await page.mouse.move(box.x + 20, box.y + 20);
  await page.mouse.down();
  await page.mouse.move(box.x + 50, box.y + 26);
  await page.mouse.up();
  expect(
    Number(await page.locator('[data-property="x"]').inputValue()),
  ).toBeGreaterThan(8);
  box = await page.locator(".handle").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 - 60,
    box.y + box.height / 2 - 12,
  );
  await page.mouse.up();
  expect(
    Number(await page.locator('[data-property="width"]').inputValue()),
  ).toBeLessThan(140);
  await page.getByRole("button", { name: "Save", exact: false }).click();
  await expect(page.getByRole("status")).toContainText("Display saved");
  await expect(page.locator("img.exact")).toBeVisible();
  await page.screenshot({
    path: "artifacts/designer-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Send to tag", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("demo_only");
  expect(errors).toEqual([]);
});
test("entity drag and drop, discovery-only tag and narrow screen", async ({
  page,
}) => {
  await page.waitForFunction(() => window.panel?.tag);
  await page.evaluate(() => {
    window.panel.document = {
      version: 1,
      elements: [],
      background: "white",
      auto_update: false,
      interval: 60,
    };
    window.panel.render();
  });
  await page
    .getByRole("combobox", { name: "Search sensors", exact: true })
    .fill("humidity");
  const source = page.locator(
    'ha-entity-picker [data-entity="sensor.office_humidity"]',
  );
  await source.dragTo(page.locator(".stage"), {
    targetPosition: { x: 35, y: 35 },
  });
  await expect(page.locator(".el")).toHaveCount(1);
  await page.getByLabel("Tag", { exact: true }).selectOption("demo-minew");
  await expect(
    page.getByRole("button", { name: "Send to tag" }),
  ).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Discovery only");
  await pickSensor(page, "sensor.office_temperature");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "artifacts/designer-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});

test("preview fits its window by default and can zoom in and out", async ({
  page,
}) => {
  await page.setViewportSize({ width: 900, height: 900 });
  await expect(page.locator(".stage")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const root = window.panel.shadowRoot;
        return (
          root.querySelector(".stage").getBoundingClientRect().width <=
          root.querySelector(".canvas-wrap").clientWidth
        );
      }),
    )
    .toBe(true);
  const before = await page.locator(".stage").boundingBox();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  expect((await page.locator(".stage").boundingBox()).width).toBeGreaterThan(
    before.width,
  );
  await page.getByRole("button", { name: "Zoom out", exact: true }).click();
  await page.getByRole("button", { name: "Fit preview", exact: true }).click();
  expect(
    Math.abs((await page.locator(".stage").boundingBox()).width - before.width),
  ).toBeLessThan(2);
});

test("sensor and text can be added when HA is served over plain HTTP", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(crypto, "randomUUID", { value: undefined }),
  );
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.waitForFunction(() => window.panel?.tag);
  await page.evaluate(() => {
    window.panel.document = {
      version: 1,
      elements: [],
      background: "white",
      auto_update: false,
      interval: 60,
    };
    window.panel.render();
  });
  await page.locator('[data-add="text"]').click();
  await expect(page.locator(".el")).toHaveCount(1);
  await pickSensor(page, "sensor.office_temperature");
  await expect(page.locator(".el")).toHaveCount(2);
  await page.locator(".el.selected").click({ button: "right" });
  await page.getByRole("menuitem", { name: "Duplicate" }).click();
  await expect(page.locator(".el")).toHaveCount(3);
  expect(errors).toEqual([]);
});

test("side panels collapse independently and expand the preview", async ({
  page,
}) => {
  await expect(page.locator(".stage")).toBeVisible();
  const before = (await page.locator(".canvas-wrap").boundingBox()).width;
  await page.getByRole("button", { name: "Toggle entities panel" }).click();
  await expect(page.locator(".library")).toBeHidden();
  await page.getByRole("button", { name: "Toggle properties panel" }).click();
  await expect(page.locator(".inspector")).toBeHidden();
  expect(
    (await page.locator(".canvas-wrap").boundingBox()).width,
  ).toBeGreaterThan(before);
  await page.getByRole("button", { name: "Toggle entities panel" }).click();
  await expect(page.locator(".library")).toBeVisible();
  await page.getByRole("button", { name: "Toggle properties panel" }).click();
  await expect(page.locator(".inspector")).toBeVisible();
});

test("unrelated HA state updates do not prevent a rendered preview", async ({
  page,
}) => {
  await page.locator('[data-add="text"]').click();
  await page.evaluate(() => {
    window.previewNoise = setInterval(() => {
      const panel = window.panel;
      panel.hass = {
        ...panel.hass,
        states: {
          ...panel.hass.states,
          "sensor.unrelated": {
            entity_id: "sensor.unrelated",
            state: String(Date.now()),
            attributes: { friendly_name: "Unrelated" },
          },
        },
      };
    }, 75);
  });
  await expect(page.locator("img.exact")).toBeVisible({ timeout: 2500 });
  await page.evaluate(() => clearInterval(window.previewNoise));
});

test("element actions are in the context menu; trash, Backspace and Delete work", async ({
  page,
}) => {
  await page.locator('[data-add="text"]').click();
  await expect(
    page.locator('.inspector [data-action="duplicate"]'),
  ).toHaveCount(0);
  await expect(page.locator("[data-preset]")).toHaveCount(0);
  await page.locator(".el.selected").click({ button: "right" });
  await expect(page.getByRole("menu")).toBeVisible();
  await page.getByRole("menuitem", { name: "Duplicate" }).click();
  await expect(page.locator(".el")).toHaveCount(2);
  await page.keyboard.press("Backspace");
  await expect(page.locator(".el")).toHaveCount(1);
  await page.getByRole("button", { name: "Undo", exact: false }).click();
  await expect(page.locator(".el")).toHaveCount(2);
  await page.locator(".layer").first().click();
  await page
    .getByRole("button", { name: "Delete selected element", exact: true })
    .click();
  await expect(page.locator(".el")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Delete selected element", exact: true }),
  ).toHaveCount(0);
  await page.locator(".layer").first().click();
  await page.keyboard.press("Delete");
  await expect(page.locator(".el")).toHaveCount(0);
});

test("typing properties updates without blur and keeps text editing shortcuts", async ({
  page,
}) => {
  await pickSensor(page, "sensor.office_temperature");
  const label = page.locator('[data-property="label"]');
  await label.fill("Living room");
  await expect(label).toBeFocused();
  await expect(page.locator(".el.selected .label")).toHaveText("Living room");
  await page.keyboard.press("Backspace");
  await expect(page.locator(".el")).toHaveCount(1);
  await expect(label).toHaveValue("Living roo");
  await expect(page.locator("img.exact")).toBeVisible();
  await expect(label).toBeFocused();
  await page.getByRole("button", { name: "Colour: red", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Colour: red", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Align center", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Align center", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("sensor type template designer saves, previews and preserves the display draft", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.locator('[data-add="text"]').click();
  await page.locator('[data-property="text"]').fill("Keep my draft");
  await page
    .getByRole("button", { name: "Sensor templates", exact: true })
    .click();
  await expect(page.getByLabel("Template", { exact: true })).toHaveValue(
    "output:numeric",
  );
  await expect(page.locator(".el")).toHaveCount(3);
  await expect(page.locator("img.exact")).toBeVisible();
  await page.locator('[data-token="unit"]').click();
  await page.locator('[data-property="text"]').fill("{{state}} {{unit}}");
  await page.getByRole("button", { name: "Save", exact: false }).click();
  await expect(page.getByRole("status")).toContainText("Template saved");
  await page.getByRole("button", { name: "Display", exact: true }).click();
  await expect(page.locator(".el")).toHaveCount(1);
  await expect(page.locator('[data-property="text"]')).toHaveValue(
    "Keep my draft",
  );
  await pickSensor(page, "sensor.office_temperature");
  await expect(page.locator("img.exact")).toBeVisible();
  await page
    .getByRole("button", { name: "Sensor templates", exact: true })
    .click();
  await page
    .getByLabel("Template", { exact: true })
    .selectOption("output:binary");
  await expect(page.locator(".el")).toHaveCount(2);
  await page.locator(".layer").last().click();
  await expect(page.getByLabel("Icon name", { exact: true })).toHaveValue(
    "{{icon}}",
  );
  await page
    .getByRole("button", { name: "Choose icon for on", exact: true })
    .click();
  await page.getByLabel("Search icons", { exact: true }).fill("window-open");
  await page
    .getByRole("button", { name: "mdi:window-open", exact: true })
    .click();
  expect(await page.evaluate(() => window.panel.element.state_icons.on)).toBe(
    "mdi:window-open",
  );
  await page.getByRole("button", { name: "Save", exact: false }).click();
  await expect(page.getByRole("status")).toContainText("Template saved");
  await page.screenshot({
    path: "artifacts/template-designer.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("weather uses an icon and offers forecast time and value selectors", async ({
  page,
}) => {
  await pickSensor(page, "weather.home");
  await expect(page.locator(".el.selected .value")).toHaveText("");
  await page
    .getByLabel("Weather time", { exact: true })
    .selectOption("tomorrow");
  await page
    .getByLabel("Weather value", { exact: true })
    .selectOption("temperature");
  await expect(page.getByLabel("Weather time", { exact: true })).toHaveValue(
    "tomorrow",
  );
  await expect(page.locator("img.exact")).toBeVisible();
});

test("icon picker font is registered and loaded in the document", async ({
  page,
}) => {
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.fonts].some(
          (font) => font.family === "LabelMDI" && font.status === "loaded",
        ),
      ),
    )
    .toBe(true);
});

test("elements can move beyond display edges without clamping", async ({
  page,
}) => {
  await page.locator('[data-add="text"]').click();
  await page.locator('[data-property="x"]').fill("-20");
  await expect
    .poll(() => page.evaluate(() => window.panel.element.x))
    .toBe(-20);
  await page.locator(".el.selected").focus();
  await page.keyboard.press("ArrowLeft");
  await expect
    .poll(() => page.evaluate(() => window.panel.element.x))
    .toBe(-21);
  await expect(page.locator("img.exact")).toBeVisible();
});

test("text can be edited directly in the preview", async ({ page }) => {
  await page.locator('[data-add="text"]').click();
  await page.locator(".el.selected .content").click();
  const editor = page.getByRole("textbox", {
    name: "Edit display text",
    exact: true,
  });
  await expect(editor).toBeFocused();
  await editor.fill("Inline °C");
  await expect(page.locator('[data-property="text"]')).toHaveValue("Inline °C");
  await page.keyboard.press("Backspace");
  await expect(page.locator(".el")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Delete");
  await expect(page.locator(".el")).toHaveCount(0);
});

test("sensor controls are conditional and canvas settings are independent", async ({
  page,
}) => {
  await pickSensor(page, "sensor.office_temperature");
  await expect(page.locator('[data-property="label"]')).toBeVisible();
  await page.locator('[data-property="show_label"]').uncheck();
  await expect(page.locator('[data-property="label"]')).toHaveCount(0);
  await page.locator('[data-property="show_unit"]').uncheck();
  await expect(page.locator('[data-property="decimals"]')).toHaveCount(0);
  await expect(page.locator(".layer-card .layers")).toBeVisible();
  expect(await page.evaluate(() => window.panel.element.background)).toBe(
    "transparent",
  );
  await pickSensor(page, "binary_sensor.window");
  await expect(page.locator('[data-property="decimals"]')).toHaveCount(0);
});

test("create template starts with the selected sensor and applies the saved style", async ({
  page,
}) => {
  await pickSensor(page, "sensor.office_temperature");
  const id = await page.evaluate(() => window.panel.selected);
  await page
    .getByLabel("Sensor template", { exact: true })
    .selectOption("__new__");
  await expect(page.getByLabel("Template name", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.panel.sampleEntity)).toBe(
    "sensor.office_temperature",
  );
  await page
    .getByLabel("Template name", { exact: true })
    .fill("My temperature");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Display", exact: true }).click();
  expect(
    await page.evaluate(
      (id) => window.panel.document.elements.find((e) => e.id === id).template,
      id,
    ),
  ).toContain(":custom:");
  await expect(
    page
      .getByLabel("Sensor template", { exact: true })
      .locator("option:checked"),
  ).toHaveText("My temperature");
});

test("shape dropdown renders each supported shape", async ({ page }) => {
  await page.getByRole("button", { name: "Add shape", exact: true }).click();
  for (const type of [
    "ellipse",
    "triangle",
    "rounded_rectangle",
    "line",
    "rectangle",
  ]) {
    await page.getByLabel("Shape", { exact: true }).selectOption(type);
    await expect
      .poll(() => page.evaluate(() => window.panel.element.type))
      .toBe(type);
    await expect(page.locator("img.exact")).toBeVisible();
  }
});

test("template mode has no send or preview button and offers every sensor", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Sensor templates", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Send to tag", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Preview", exact: true }),
  ).toHaveCount(0);
  await page
    .getByLabel("Sample sensor", { exact: true })
    .selectOption("binary_sensor.window");
  expect(await page.evaluate(() => window.panel.templateSensorType)).toBe(
    "output:binary",
  );
  await expect(page.getByLabel("Sample sensor", { exact: true })).toHaveValue(
    "binary_sensor.window",
  );
});

test("images can be uploaded, resized and used as state-specific template parts", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add image", exact: true }).click();
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aDQAAAABJRU5ErkJggg==",
    "base64",
  );
  await page
    .getByLabel("Upload image", { exact: true })
    .setInputFiles({ name: "image.png", mimeType: "image/png", buffer: png });
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.panel.element.image.startsWith("data:image/png"),
      ),
    )
    .toBe(true);
  await expect(page.locator("img.exact")).toBeVisible();
  await page.getByLabel("Image fit", { exact: true }).selectOption("fill");
  await expect(page.locator("img.exact")).toBeVisible();
  await page
    .getByRole("button", { name: "Sensor templates", exact: true })
    .click();
  await page.getByRole("button", { name: "Add image", exact: true }).click();
  await page.getByLabel("Visible state", { exact: true }).fill("on");
  expect(await page.evaluate(() => window.panel.element.state)).toBe("on");
});

test("slow previews never overlap and render the latest edit", async ({
  page,
}) => {
  await page.waitForTimeout(250);
  await page.evaluate(() => {
    window.activePreviews = window.peakPreviews = 0;
    window.panel.previewRequest = async () => {
      window.activePreviews++;
      window.peakPreviews = Math.max(
        window.peakPreviews,
        window.activePreviews,
      );
      await new Promise((resolve) => setTimeout(resolve, 650));
      window.activePreviews--;
      return {
        png: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aDQAAAABJRU5ErkJggg==",
        layers: {},
      };
    };
  });
  for (let i = 0; i < 4; i++) {
    await page.evaluate(() => window.panel.queuePreview());
    await page.waitForTimeout(250);
  }
  await expect
    .poll(() => page.evaluate(() => window.activePreviews), { timeout: 4000 })
    .toBe(0);
  expect(await page.evaluate(() => window.peakPreviews)).toBe(1);
  await expect(page.locator("img.exact")).toBeVisible();
});
