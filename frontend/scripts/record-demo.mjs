// Records the two-session demo as a video, driving the real app in a browser.
// Needs the backend (with LLM_API_KEY) on :8000 and the frontend on :3000.
// Run from frontend/:  node scripts/record-demo.mjs   ->  ../docs/demo/socratic-demo.webm
import { renameSync } from "node:fs";
import { chromium } from "playwright";

const APP_URL = "http://localhost:3000";
const OUTPUT = "../docs/demo/socratic-demo.webm";
const READING_PAUSE_MS = 2500; // time for a viewer to read each step
const RATE_LIMIT_PAUSE_MS = 9000; // stays under the free tier's tokens-per-minute limit
const LLM_TIMEOUT_MS = 120_000;

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: "../docs/demo/", size: { width: 1280, height: 800 } },
});
const page = await context.newPage();
const pause = (ms = READING_PAUSE_MS) => page.waitForTimeout(ms);

async function type(selector, text) {
  await page.fill(selector, text);
  await pause(800);
  await page.press(selector, "Enter");
}

async function startSession(topic) {
  await page.waitForTimeout(RATE_LIMIT_PAUSE_MS);
  await type("#topic", topic);
  await page.waitForURL(/\/sessions\/\d+$/, { timeout: LLM_TIMEOUT_MS });
  await page.waitForSelector("ol > li", { timeout: LLM_TIMEOUT_MS });
  await pause(4000);
}

async function send(text) {
  await page.waitForTimeout(RATE_LIMIT_PAUSE_MS);
  const messagesBefore = await page.locator("ol > li").count();
  await type("#message", text);
  // Done when both new messages are shown and the "thinking" line is gone.
  await page.waitForFunction(
    (count) =>
      document.querySelectorAll("ol > li").length >= count + 2 &&
      !document.body.innerText.includes("Tutor is thinking"),
    messagesBefore,
    { timeout: LLM_TIMEOUT_MS },
  );
  await pause(4000);
}

async function endSession() {
  await page.waitForTimeout(RATE_LIMIT_PAUSE_MS);
  await page.click("text=End session");
  await page.waitForSelector("text=What I learned about you", { timeout: LLM_TIMEOUT_MS });
  await pause(5000);
}

await page.goto(APP_URL);
await pause();
await type("#name", "Alex");
await page.click("a:has-text('Alex')");
await page.waitForSelector("#topic");
await pause();

await startSession("Adding fractions");
await send("I think 1/2 + 1/3 = 2/5. You just add the tops and the bottoms.");
await send("Oh, 2/5 is smaller than 1/2, so that can't be right. I'm not sure how to do it then.");
await endSession();

await page.click("text=Review or correct these notes");
await page.waitForSelector("text=What the tutor remembers");
await pause(5000);

await page.click("text=Sessions");
await page.waitForSelector("#topic");
await startSession("Adding fractions");
await send("Last time I added the tops and bottoms. Now: 1/2 is 3/6 and 1/3 is 2/6, so it's 5/6!");
await endSession();

await page.click("text=Review or correct these notes");
await page.waitForSelector("text=What the tutor remembers");
await pause(6000);

const video = page.video();
await context.close(); // the video file is written when the context closes
renameSync(await video.path(), OUTPUT);
await browser.close();
console.log(`Saved ${OUTPUT}`);
