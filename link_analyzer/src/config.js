const port = parseInt(process.env.PORT || '3000', 10);
const enableCua = (process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const cuaEnabled = (process.env.CUA_ENABLED || process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const llmApiKey = process.env.LLM_API_KEY || '';
const llmModel = process.env.LLM_MODEL || 'gpt-3.5-turbo';
const llmBaseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1';

const browserbaseApiKey = process.env.BROWSERBASE_API_KEY || '';
const browserbaseProjectId = process.env.BROWSERBASE_PROJECT_ID || '';
const useBrowserbaseForCua = (process.env.USE_BROWSERBASE_FOR_CUA || 'true').toLowerCase() === 'true';

const cuaApiKey = process.env.CUA_API_KEY || '';
const cuaModel = process.env.CUA_MODEL || '';
const cuaBaseUrl = process.env.CUA_BASE_URL || '';
const cuaMaxSteps = parseInt(process.env.CUA_MAX_STEPS || '12', 10);
const cuaMaxTokens = parseInt(process.env.CUA_MAX_TOKENS || '4000', 10);

module.exports = {
  port,
  enableCua,
  cuaEnabled,
  llmApiKey,
  llmModel,
  llmBaseUrl,
  browserbaseApiKey,
  browserbaseProjectId,
  useBrowserbaseForCua,
  cuaApiKey,
  cuaModel,
  cuaBaseUrl,
  cuaMaxSteps,
  cuaMaxTokens,
};
