import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parse } from "@babel/parser";
import { handleCardKeyDown } from "../src/lib/cardInteraction.mjs";
import { confirmEntryDeletion } from "../src/lib/entryInteraction.mjs";

const read = (name) => readFileSync(new URL(`../src/components/${name}`, import.meta.url), "utf8");
const attributes = (node) => new Map(node.openingElement.attributes
  .filter((attribute) => attribute.type === "JSXAttribute")
  .map((attribute) => [attribute.name.name, attribute.value]));
const elements = (source) => {
  const found = [];
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    if (node.type === "JSXElement") found.push(node);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === "object") visit(value);
    }
  };
  visit(typeof source === "string" ? parse(source, { sourceType: "module", plugins: ["jsx"] }) : source);
  return found;
};

test("interactive KPI cards have button semantics, visible focus, and no nested controls", () => {
  const source = read("Dashboard.jsx");
  const cards = elements(source).filter((node) => node.openingElement.name.name === "Card");
  const interactive = cards.filter((node) => attributes(node).has("onClick"));
  assert.equal(interactive.length, 2); // Five MetricCard instances and the Ads ROI card.
  for (const card of interactive) {
    const attrs = attributes(card);
    assert.equal(attrs.get("role")?.value, "button");
    assert.equal(attrs.get("tabIndex")?.expression?.value, 0);
    for (const name of ["aria-label", "aria-haspopup", "onKeyDown"]) assert.ok(attrs.has(name), name);
    assert.equal(elements(card.children).filter((node) => node.openingElement.name.name === "button").length, 0);
  }
  assert.match(source, /focus-visible:ring-2/);
  assert.match(source, /motion-reduce:animate-none/);
  assert.equal(cards.filter((node) => !attributes(node).has("onClick") && attributes(node).has("role")).length, 0);
});

test("Enter and Space activate once; other keys and repeats do not", () => {
  let activations = 0;
  const event = (key, repeat = false) => ({ key, repeat, prevented: false, preventDefault() { this.prevented = true; } });
  for (const key of ["Enter", " "]) {
    const press = event(key);
    handleCardKeyDown(press, () => activations++);
    assert.equal(press.prevented, true);
  }
  assert.equal(activations, 2);
  handleCardKeyDown(event("Enter", true), () => activations++);
  handleCardKeyDown(event("ArrowDown"), () => activations++);
  assert.equal(activations, 2);
});

test("delete control names its entry and cancellation prevents deletion", () => {
  const source = read("DailyInput.jsx");
  const deleteButton = elements(source).find((node) => attributes(node).get("data-testid")?.value === "entry-delete");
  assert.ok(deleteButton);
  const attrs = attributes(deleteButton);
  assert.ok(attrs.has("aria-label"));
  assert.ok(attrs.has("onClick"));
  assert.match(source, /confirmEntryDeletion\(\(message\) => window\.confirm\(message\), deleteLabel, \(\) => onDelete\(e\.id\)\)/);
  assert.match(source, /e\.data\.account \|\| e\.data\.name \|\| e\.data\.streamer \|\| e\.data\.type/);
  let deleted = 0;
  let prompt = "";
  confirmEntryDeletion((message) => { prompt = message; return false; }, "Hapus entri Penjualan Toko A tanggal 2026-10-16", () => deleted++);
  assert.equal(deleted, 0);
  assert.equal(prompt, "Hapus entri Penjualan Toko A tanggal 2026-10-16?");
  confirmEntryDeletion(() => true, "Hapus entri Penjualan Toko A tanggal 2026-10-16", () => deleted++);
  assert.equal(deleted, 1);
});

test("small KPI card text reaches WCAG AA contrast on existing surface", () => {
  const luminance = (hex) => {
    const rgb = hex.match(/[0-9a-f]{2}/gi).map((part) => parseInt(part, 16) / 255);
    const linear = rgb.map((part) => part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4);
    return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
  };
  const foreground = luminance("94a3b8"); // Existing slate-400 token.
  const background = luminance("161f30"); // Existing KPI card surface.
  assert.ok((foreground + 0.05) / (background + 0.05) >= 4.5);
  assert.doesNotMatch(read("Dashboard.jsx").split('const MetricCard =')[1].split('const DetailDialog =')[0], /text-slate-500/);
});
