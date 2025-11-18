import { Stagehand } from "@browserbasehq/stagehand";
import dotenv from "dotenv";

dotenv.config();

let cachedClient: Stagehand | null = null;

export function getStagehandClient(): Stagehand {
  if (cachedClient) {
    return cachedClient;
  }

  const apiKey = process.env.BROWSERBASE_API_KEY;
  const projectId = process.env.BROWSERBASE_PROJECT_ID;
  const modelApiKey = process.env.MODEL_API_KEY;
  const stagehandApiUrl = process.env.STAGEHAND_API_URL;
  const modelName = process.env.STAGEHAND_MODEL_NAME ?? "gpt-4o";

  if (!apiKey) {
    throw new Error("BROWSERBASE_API_KEY is required for Stagehand client");
  }

  if (!projectId) {
    throw new Error("BROWSERBASE_PROJECT_ID is required for Stagehand client");
  }

  cachedClient = new Stagehand({
    apiKey,
    projectId,
    modelName,
    apiUrl: stagehandApiUrl,
    modelApiKey,
  });

  return cachedClient;
}
