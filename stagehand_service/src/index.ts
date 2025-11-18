import "dotenv/config";
import express from "express";
import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod/v3";

const app = express();
app.use(express.json());

const requestSchema = z.object({
  url: z.string().url(),
});

interface ParsedPage {
  title: string | null;
  content: string | null;
  url: string;
}

interface StagehandPage {
  goto?: (url: string, options?: Record<string, unknown>) => Promise<unknown>;
  title?: () => Promise<string>;
  evaluate?: <T>(fn: () => T) => Promise<T>;
}

interface StagehandSession {
  page?: StagehandPage;
  close?: () => Promise<void>;
  browser?: { close?: () => Promise<void> };
}

function createStagehand() {
  const apiKey = process.env.BROWSERBASE_API_KEY;
  if (!apiKey) {
    throw new Error("BROWSERBASE_API_KEY is not configured");
  }

  return new Stagehand({
    apiKey,
    // Allow overriding the LLM model while keeping a sensible default.
    modelName: process.env.STAGEHAND_MODEL ?? process.env.OPENAI_MODEL ?? "gpt-4o-mini",
    openaiApiKey: process.env.OPENAI_API_KEY,
    browserbase: {
      projectId: process.env.BROWSERBASE_PROJECT_ID,
    },
  } as Record<string, unknown>);
}

app.post("/parse", async (req, res) => {
  const parsedBody = requestSchema.safeParse(req.body);
  if (!parsedBody.success) {
    return res.status(400).json({
      success: false,
      error: "Invalid request body",
      details: parsedBody.error.flatten(),
    });
  }

  const { url } = parsedBody.data;

  try {
    const stagehand = createStagehand();
    const session = (await (stagehand as unknown as { start: (options?: Record<string, unknown>) => Promise<StagehandSession> }).start({
      // Browser runtime is configured in Stagehand; we request a headless chromium instance.
      headless: true,
    })) as StagehandSession;

    const page: StagehandPage | undefined = session.page ?? (session as unknown as StagehandPage);
    if (!page || typeof page.goto !== "function") {
      throw new Error("Stagehand session did not provide a browser page");
    }

    await page.goto(url, { waitUntil: "networkidle" });

    const title = typeof page.title === "function" ? await page.title() : null;
    const content = typeof page.evaluate === "function"
      ? await page.evaluate(() => document.body?.innerText?.slice(0, 8000) ?? null)
      : null;

    if (typeof session.close === "function") {
      await session.close();
    } else if (session.browser && typeof session.browser.close === "function") {
      await session.browser.close();
    }

    const result: ParsedPage = { title, content, url };

    return res.json({ success: true, data: result });
  } catch (error) {
    console.error("Stagehand parse error", error);
    return res.status(500).json({ success: false, error: "Failed to parse page" });
  }
});

const port = Number.parseInt(process.env.PORT ?? "3000", 10);
app.listen(port, () => {
  console.log(`Stagehand service listening on port ${port}`);
});
