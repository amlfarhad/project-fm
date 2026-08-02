import { mkdir, mkdtemp, readFile, readdir, rm, stat } from "node:fs/promises";
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
let activeClient = null;

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
  activeClient = client;
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Log.enable");
  await client.send("Network.enable");
  const downloadDir = join(userDataDir, "downloads");
  await mkdir(downloadDir, { recursive: true });
  await client.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: downloadDir });
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
    await waitForText(client, "Public domain");
    await waitForText(client, "OpenCV");
    await waitForText(client, "real video");
    const hostedVideoReady = await waitForExpression(
      client,
      `(() => { const video = document.querySelector("video.source-video"); return Boolean(video && video.readyState >= 1 && video.duration > 0); })()`,
      "Repository sample video did not load",
    );
    if (!hostedVideoReady) throw new Error("Repository sample video did not load");
    const hostedStatusCounts = await evaluate(
      client,
      `JSON.stringify({
        observed: document.querySelectorAll(".player-state-observed, .position-status-observed").length,
        inferred: document.querySelectorAll(".player-state-inferred, .position-status-inferred").length
      })`,
    );
    const parsedHostedStatusCounts = JSON.parse(hostedStatusCounts);
    if (parsedHostedStatusCounts.observed < 1 || parsedHostedStatusCounts.inferred < 1) {
      throw new Error(`Hosted proof did not render observed and inferred positions: ${hostedStatusCounts}`);
    }
    await evaluate(client, `(() => { const range = document.querySelector('input[type="range"]'); if (!range) throw new Error("Timeline control missing"); range.value = range.max; range.dispatchEvent(new Event("input", { bubbles: true })); range.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    await seedCorrectionName(client);
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => (button.getAttribute("aria-label") || "").startsWith("Save correction")).click()`);
    let correctionSaved = false;
    for (let index = 0; index < 20; index += 1) {
      correctionSaved = await evaluate(client, `Boolean(document.querySelector(".position-status-corrected"))`);
      if (correctionSaved) break;
      await delay(50);
    }
    if (!correctionSaved) throw new Error("Correction did not persist in hosted proof");
    const hostedCsv = await clickExportAndVerify(client, downloadDir, "CSV");
    const hostedCsvBody = await readFile(hostedCsv, "utf8");
    if (!hostedCsvBody.includes('"Analyst, Sample"')) {
      throw new Error(`Hosted CSV did not preserve a comma-containing analyst name as one cell: ${hostedCsvBody.slice(0, 500)}`);
    }
    await clickExportAndVerify(client, downloadDir, "JSONL");
  } else {
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.includes("Open analyst console")).click()`);
    await waitForText(client, "File Ingest");
    await waitForText(client, "Browser Capture");
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.includes("Process repository sample")).click()`);
    await waitForText(client, "Evidence and provenance");
    await waitForText(client, "OpenCV");
    const localVideoReady = await waitForExpression(
      client,
      `(() => { const video = document.querySelector("video.source-video"); return Boolean(video && video.readyState >= 1 && video.duration > 0); })()`,
      "Repository sample video did not load in local mode",
    );
    if (!localVideoReady) throw new Error("Repository sample video did not load in local mode");
    await waitForExpression(
      client,
      `document.querySelectorAll(".player-state-observed, .position-status-observed").length > 0 && document.querySelectorAll(".player-state-inferred, .position-status-inferred").length > 0`,
      "Local pipeline did not finish rendering observed and inferred positions",
    );
    const localStatusCounts = await evaluate(
      client,
      `JSON.stringify({
        observed: document.querySelectorAll(".player-state-observed, .position-status-observed").length,
        inferred: document.querySelectorAll(".player-state-inferred, .position-status-inferred").length
      })`,
    );
    const parsedLocalStatusCounts = JSON.parse(localStatusCounts);
    if (parsedLocalStatusCounts.observed < 1 || parsedLocalStatusCounts.inferred < 1) {
      throw new Error(`Local pipeline did not render observed and inferred positions: ${localStatusCounts}`);
    }
    await seedCorrectionName(client);
    await evaluate(client, `Array.from(document.querySelectorAll("button")).find((button) => (button.getAttribute("aria-label") || "").startsWith("Save correction")).click()`);
    let correctionSaved = false;
    for (let index = 0; index < 20; index += 1) {
      correctionSaved = await evaluate(client, `Boolean(document.querySelector(".position-status-corrected"))`);
      if (correctionSaved) break;
      await delay(50);
    }
    if (!correctionSaved) throw new Error("Correction did not persist in local pipeline");
    const localCsv = await clickExportAndVerify(client, downloadDir, "CSV");
    const localCsvBody = await readFile(localCsv, "utf8");
    if (!localCsvBody.includes('"Analyst, Sample"')) {
      throw new Error(`Local CSV did not preserve a comma-containing analyst name as one cell: ${localCsvBody.slice(0, 500)}`);
    }
    await clickExportAndVerify(client, downloadDir, "JSONL");
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
  const consoleErrors = client.events.filter(
    (event) => event.method === "Log.entryAdded" && ["error", "assert"].includes(event.params?.entry?.level),
  );
  const requestUrls = new Map(
    client.events
      .filter((event) => event.method === "Network.requestWillBeSent")
      .map((event) => [event.params.requestId, event.params.request.url]),
  );
  const networkFailures = client.events.filter((event) => {
    if (event.method !== "Network.loadingFailed") return false;
    const url = requestUrls.get(event.params.requestId) ?? "";
    return !(event.params.errorText === "net::ERR_ABORTED" && /\.(mp4|webm|ogv)(?:\?|$)/i.test(url));
  });
  if (exceptionCount > 0 || consoleErrors.length > 0 || networkFailures.length > 0) {
    throw new Error(
      `Browser errors: runtime=${exceptionCount}, console=${JSON.stringify(consoleErrors.map((event) => ({ text: event.params.entry.text, url: event.params.entry.url })))}, network=${JSON.stringify(networkFailures.map((event) => ({ url: requestUrls.get(event.params.requestId), error: event.params.errorText })))}`,
    );
  }
  client.close();
  console.log("Project FM browser smoke complete.");
} finally {
  activeClient?.close();
  chrome.kill("SIGKILL");
  await delay(100);
  await rm(userDataDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}

async function waitForExpression(client, expression, message, attempts = 100) {
  for (let index = 0; index < attempts; index += 1) {
    if (await evaluate(client, expression)) return true;
    await delay(100);
  }
  throw new Error(message);
}

async function clickExportAndVerify(client, downloadDir, label) {
  const extension = label.toLowerCase();
  await evaluate(
    client,
    `Array.from(document.querySelectorAll("button")).find((button) => button.innerText.trim() === ${JSON.stringify(label)}).click()`,
  );
  for (let index = 0; index < 80; index += 1) {
    const files = await readdir(downloadDir);
    const candidate = files.find((file) => file.endsWith(`.${extension}`) && !file.endsWith(".crdownload"));
    if (candidate) {
      const downloaded = await stat(join(downloadDir, candidate));
      if (downloaded.size > 0) return join(downloadDir, candidate);
    }
    await delay(100);
  }
  throw new Error(`Export download did not complete: ${label}`);
}

async function seedCorrectionName(client) {
  const value = await evaluate(
    client,
    `(() => {
      const input = document.querySelector('input[aria-label^="Player name for"]');
      if (!input) throw new Error("Player name correction control missing");
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
      setter.call(input, "Analyst, Sample");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return input.value;
    })()`,
  );
  await delay(250);
  const settledValue = await evaluate(client, `document.querySelector('input[aria-label^="Player name for"]').value`);
  if (settledValue !== "Analyst, Sample" || value !== "Analyst, Sample") {
    throw new Error(`Player name correction input did not receive test text: ${JSON.stringify({ value, settledValue })}`);
  }
}
