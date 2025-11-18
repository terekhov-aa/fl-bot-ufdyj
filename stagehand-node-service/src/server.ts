import express, { Request, Response } from "express";
import dotenv from "dotenv";
import { getStagehandClient } from "./stagehandClient.js";
import { URL } from "node:url";

dotenv.config();

const app = express();
app.use(express.json({ limit: "1mb" }));

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

function validateUrl(url: unknown): string {
  if (typeof url !== "string" || url.trim() === "") {
    throw new Error("url is required and must be a non-empty string");
  }
  try {
    const parsed = new URL(url);
    if (!/^https?:$/.test(parsed.protocol)) {
      throw new Error("Only http/https protocols are allowed");
    }
    return parsed.toString();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Invalid URL";
    throw new Error(message);
  }
}

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok" });
});

app.post("/stagehand/extract", async (req: Request, res: Response) => {
  try {
    const { url, instruction, schema, options } = req.body ?? {};
    const validatedUrl = validateUrl(url);

    const client = getStagehandClient();
    const browser = await client.init({ mode: "remote" });
    const page = await browser.newPage();

    await page.goto(validatedUrl, { waitUntil: "networkidle" });
    const result = await page.extract({
      instruction: instruction ?? "Extract the main content of the page as structured data.",
      schema,
      options,
    });

    await browser.close();
    res.json({ result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    const status = message.toLowerCase().includes("url") ? 400 : 500;
    res.status(status).json({ error: message });
  }
});

app.use((err: unknown, _req: Request, res: Response, _next: unknown) => {
  console.error(err);
  res.status(500).json({ error: "Internal server error" });
});

app.listen(PORT, () => {
  console.log(`Stagehand service listening on port ${PORT}`);
});
