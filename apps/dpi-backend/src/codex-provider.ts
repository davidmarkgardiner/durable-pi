import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { openaiCodexProvider } from "@earendil-works/pi-ai/providers/openai-codex";

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw Error("Invalid Codex authentication data. Run codex login.");
  }
}

export function readCodexAccessToken(path: string): string {
  const auth = parseJson(readFileSync(path, "utf8"));
  if (!auth || typeof auth !== "object" || !("tokens" in auth))
    throw Error("Codex ChatGPT login is missing. Run codex login.");
  const tokens = auth.tokens;
  if (!tokens || typeof tokens !== "object" || !("access_token" in tokens) || typeof tokens.access_token !== "string")
    throw Error("Codex ChatGPT access token is missing. Run codex login.");
  const payload = tokens.access_token.split(".")[1];
  if (!payload) throw Error("Invalid Codex access token. Run codex login.");
  const claims = parseJson(Buffer.from(payload, "base64url").toString("utf8"));
  if (!claims || typeof claims !== "object" || !("exp" in claims) || typeof claims.exp !== "number")
    throw Error("Codex access token has no expiry. Run codex login.");
  if (claims.exp * 1000 <= Date.now())
    throw Error("Codex access token expired. Use Codex to refresh its login, then retry.");
  return tokens.access_token;
}

export function localCodexProvider(path = process.env.DPI_CODEX_AUTH_FILE ?? join(homedir(), ".codex", "auth.json")) {
  const provider = openaiCodexProvider();
  return {
    ...provider,
    auth: {
      apiKey: {
        name: "Local Codex OAuth",
        resolve: async () => ({ auth: { apiKey: readCodexAccessToken(path) }, source: "Codex OAuth" }),
      },
    },
  };
}
