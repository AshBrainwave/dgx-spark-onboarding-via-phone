import { gzipSync } from "node:zlib";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distRoot = resolve(appRoot, "dist");
const output = resolve(appRoot, "../agent/sparkd_provision/portal/static/index.html");
let html = await readFile(resolve(distRoot, "index.html"), "utf8");

const scriptTag = html.match(/<script type="module" crossorigin src="([^"]+)"><\/script>/);
const styleTag = html.match(/<link rel="stylesheet" crossorigin href="([^"]+)">/);
if (!scriptTag || !styleTag) throw new Error("Vite output did not contain one script and stylesheet");

const asset = async (relativePath) =>
  readFile(resolve(distRoot, relativePath.replace(/^\.\//, "")), "utf8");
const javascript = (await asset(scriptTag[1])).replaceAll("</script", "<\\/script");
const css = (await asset(styleTag[1])).replaceAll("</style", "<\\/style");
html = html.replace(scriptTag[0], () => `<script type="module">${javascript}</script>`);
html = html.replace(styleTag[0], () => `<style>${css}</style>`);
const markupOnly = html.replace(/<script\b[\s\S]*?<\/script>/g, "").replace(/<style\b[\s\S]*?<\/style>/g, "");
if (/\b(?:src|href)=["'](?:https?:|\/|\.\/assets\/)/.test(markupOnly)) {
  throw new Error("Portal bundle still contains an external asset reference");
}
const gzipBytes = gzipSync(html).byteLength;
if (gzipBytes > 300 * 1024) throw new Error(`Portal bundle is ${gzipBytes} bytes gzipped`);
await mkdir(dirname(output), { recursive: true });
await writeFile(output, html);
await rm(distRoot, { recursive: true, force: true });
console.log(`Wrote ${output} (${html.length} bytes, ${gzipBytes} bytes gzipped)`);
