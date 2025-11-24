const port = parseInt(process.env.PORT || '3000', 10);
const enableCua = (process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const llmApiKey = process.env.LLM_API_KEY || '';
const llmModel = process.env.LLM_MODEL || 'gpt-3.5-turbo';
const llmBaseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1';
const cuaBaseUrl = process.env.CUA_BASE_URL || '';
const cuaApiKey = process.env.CUA_API_KEY || '';
const cuaModel = process.env.CUA_MODEL || '';
const browserbaseApiKey = process.env.BROWSERBASE_API_KEY || '';
const browserbaseProjectId = process.env.BROWSERBASE_PROJECT_ID || '';

module.exports = {
  port,
  enableCua,
  llmApiKey,
  llmModel,
  llmBaseUrl,
  cuaBaseUrl,
  cuaApiKey,
  cuaModel,
  browserbaseApiKey,
  browserbaseProjectId,
};
