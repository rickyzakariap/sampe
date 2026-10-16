import { after, test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { transformWithOxc } from "vite";

const tempDir = await mkdtemp(join(process.cwd(), ".ai-markdown-test-"));
after(() => rm(tempDir, { recursive: true, force: true }));
const output = join(tempDir, "AiMarkdown.mjs");
const sourcePath = join(process.cwd(), "src/components/AiMarkdown.jsx");
const { code } = await transformWithOxc(await readFile(sourcePath, "utf8"), sourcePath,
  { lang: "jsx", jsx: { runtime: "automatic" } });
await writeFile(output, code);
const { AiMarkdown } = await import(pathToFileURL(output).href);

const render = (text) => renderToStaticMarkup(React.createElement(AiMarkdown, { text }));

test("AI headings, emphasis, lists, and existing plain text render consistently", () => {
  const html = render("**KONDISI SAAT INI:**\n\n- **Penjualan** tertinggal\n\n**REKOMENDASI AKSI:**\n\n1. Periksa target\n2. Catat realisasi\n\nBaris pertama  \nBaris kedua");
  assert.match(html, /<h3[^>]*>KONDISI SAAT INI<\/h3>/);
  assert.match(html, /<strong[^>]*>Penjualan<\/strong>/);
  assert.match(html, /<ul[^>]*>/);
  assert.match(html, /<ol[^>]*>/);
  assert.match(html, /<br\s*\/?\s*>/);
  assert.doesNotMatch(html, /\*\*KONDISI/);
  assert.match(render("Analisis lama tetap terbaca."), /Analisis lama tetap terbaca/);
});

test("untrusted AI output cannot inject HTML, scripts, or external links", () => {
  const html = render("Aman\n\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[jalan](javascript:alert(1))");
  assert.match(html, /Aman/);
  assert.doesNotMatch(html, /<script|<img|<a\s|onerror=|javascript:/i);
});
