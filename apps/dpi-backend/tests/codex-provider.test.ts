import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readCodexAccessToken } from "../src/codex-provider.js";

test("Codex auth is reread after rotation and never modified", () => {
  const dir = mkdtempSync(join(tmpdir(), "dpi-codex-auth-"));
  const path = join(dir, "auth.json");
  const token = (signature: string, exp: number) =>
    `test.${Buffer.from(JSON.stringify({ exp })).toString("base64url")}.${signature}`;
  const save = (access_token: string) => {
    const content = JSON.stringify({ tokens: { access_token, refresh_token: "must-stay-untouched" } });
    writeFileSync(path, content, { mode: 0o600 });
    return content;
  };
  try {
    const first = token("first", Date.now() / 1000 + 3600);
    const original = save(first);
    assert.equal(readCodexAccessToken(path), first);
    assert.equal(readFileSync(path, "utf8"), original);
    const second = token("second", Date.now() / 1000 + 3600);
    save(second);
    assert.equal(readCodexAccessToken(path), second);
    save(token("expired", 1));
    assert.throws(() => readCodexAccessToken(path), /expired/);
    writeFileSync(path, JSON.stringify({ tokens: {} }));
    assert.throws(() => readCodexAccessToken(path), /missing/);
    writeFileSync(path, '{"secret":"do-not-log-this');
    assert.throws(() => readCodexAccessToken(path), { message: "Invalid Codex authentication data. Run codex login." });
  } finally {
    rmSync(dir, { recursive: true });
  }
});
