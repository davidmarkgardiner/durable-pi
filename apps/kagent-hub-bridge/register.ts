import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { NetworkRegistry } from "../dpi-sdk/src/node/registry.js";
const token = readFileSync(fileURLToPath(new URL(".data/bridge.token", import.meta.url)), "utf8").trim();
const registry = new NetworkRegistry();
registry.upsert({ id: "kagent-proxmox", name: "Native kagent on Proxmox", kind: "url", url: "http://127.0.0.1:4798", source: "config", token });
console.log("Registered kagent-proxmox at http://127.0.0.1:4798; token kept in the local registry.");
registry.db.close();
