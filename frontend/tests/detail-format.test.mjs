import { test } from "node:test";
import assert from "node:assert/strict";
import { detailPercent, displayNumber } from "../src/lib/detailFormat.mjs";

test("detail percentages use Indonesian formatting with at most one decimal", () => {
  assert.equal(detailPercent(55.5555555556), "55,6%");
  assert.equal(detailPercent(33.3333333333), "33,3%");
  assert.equal(detailPercent(0), "0%");
  assert.equal(detailPercent(1234567.89), "1.234.567,9%");
  assert.equal(detailPercent("not-a-number"), "Tidak tersedia");
});

test("dashboard numbers use Indonesian decimals without unnecessary zeroes", () => {
  assert.equal(displayNumber(30), "30");
  assert.equal(displayNumber(3.5, 2), "3,5");
  assert.equal(displayNumber(3.56, 2), "3,56");
  assert.equal(detailPercent(53.333333), "53,3%");
  assert.equal(displayNumber(1234567.5), "1.234.567,5");
});
