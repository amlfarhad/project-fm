import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const appUrl = process.env.PROJECT_FM_FRONTEND_URL ?? "http://127.0.0.1:5173";
const port = Number(process.env.PROJECT_FM_CHROME_DEBUG_PORT ?? 9333);

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForJson(url, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return response.json();
      }
    } catch {
      // Chrome is still starting.
    }
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function cdp(wsUrl) {
  const socket = new WebSocket(wsUrl);
  const pending = new Map();
  let nextId = 1;
  const events = [];
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data.toString());
    if (payload.id && pending.has(payload.id)) {
      const { resolve, reject } = pending.get(payload.id);
      pending.delete(payload.id);
      if (payload.error) {
        reject(new Error(payload.error.message));
      } else {
        resolve(payload.result);
      }
      return;
    }
    events.push(payload);
  });
  return {
    events,
    send(method, params = {}) {
      const id = nextId;
      nextId += 1;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
      });
    },
    close() {
      socket.close();
    },
  };
}

async function waitForText(client, text, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    const result = await client.send("Runtime.evaluate", {
      expression: `document.body && document.body.innerText.includes(${JSON.stringify(text)})`,
      returnByValue: true,
    });
    if (result.result.value === true) {
      return;
    }
    await delay(100);
  }
  const snapshot = await client.send("Runtime.evaluate", {
    expression: "JSON.stringify({ url: location.href, readyState: document.readyState, text: document.body ? document.body.innerText.slice(0, 1000) : '', html: document.body ? document.body.outerHTML.slice(0, 1000) : '' })",
    returnByValue: true,
  });
  throw new Error(`Missing rendered text: ${text}\nRendered text: ${snapshot.result.value}`);
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", { expression, returnByValue: true });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text);
  }
  return result.result.value;
}

const userDataDir = await mkdtemp(join(tmpdir(), "project-fm-chrome-"));
const chrome = spawn(chromePath, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${userDataDir}`,
  "about:blank",
], { stdio: "ignore" });

try {
  await waitForJson(`http://127.0.0.1:${port}/json/list`);
  const newTabResponse = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(appUrl)}`, {
    method: "PUT",
  });
  if (!newTabResponse.ok) {
    throw new Error(`Could not create Chrome tab: ${newTabResponse.status}`);
  }
  const tab = await newTabResponse.json();
  const client = await cdp(tab.webSocketDebuggerUrl);
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await client.send("Page.navigate", { url: appUrl });
  for (let index = 0; index < 80; index += 1) {
    const readyState = await evaluate(client, "document.readyState");
    if (readyState === "complete" || readyState === "interactive") {
      break;
    }
    await delay(100);
  }
  await waitForText(client, "Open the repository sample");
  if (process.env.PROJECT_FM_EXPECT_HOSTED === "1") {
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.includes("Open the repository sample")).click()`);
    await waitForText(client, "precomputed proof");
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.trim() === "Analyst").click()`);
    await waitForText(client, "Evidence and provenance");
    await evaluate(client, `(() => { const range = document.querySelector('input[type="range"]'); if (!range) throw new Error("Timeline control missing"); range.value = range.max; range.dispatchEvent(new Event("input", { bubbles: true })); range.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => (button.getAttribute("aria-label") || "").startsWith("Save correction")).click()`);
    let correctionSaved = false;
    for (let index = 0; index < 20; index += 1) {
      correctionSaved = await evaluate(client, `Boolean(document.querySelector(".position-status-corrected"))`);
      if (correctionSaved) break;
      await delay(50);
    }
    if (!correctionSaved) throw new Error("Correction did not persist in hosted proof");
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.trim() === "CSV").click()`);
  } else {
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.includes("Open analyst console")).click()`);
    await waitForText(client, "File Ingest");
    await waitForText(client, "Browser Capture");
  }
  const desktopWidth = await evaluate(client, "document.documentElement.scrollWidth");
  if (desktopWidth > 1440) {
    throw new Error(`Desktop layout overflowed: ${desktopWidth}px`);
  }
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true,
  });
  await delay(250);
  const mobileWidth = await evaluate(client, "document.documentElement.scrollWidth");
  if (mobileWidth > 390) {
    throw new Error(`Mobile layout overflowed: ${mobileWidth}px`);
  }
  const exceptionCount = client.events.filter((event) => event.method === "Runtime.exceptionThrown").length;
  if (exceptionCount > 0) {
    throw new Error(`Browser runtime exceptions: ${exceptionCount}`);
  }
  client.close();
  console.log("Project FM browser smoke complete.");
} finally {
  chrome.kill("SIGTERM");
  await rm(userDataDir, { recursive: true, force: true });
}
