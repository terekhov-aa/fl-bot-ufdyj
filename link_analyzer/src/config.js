// FILE: link_analyzer/src/config.js
const port = parseInt(process.env.PORT || '3000', 10);

// флаги CUA
const enableCua = (process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const cuaEnabledFlag = (process.env.CUA_ENABLED || '').toLowerCase() === 'true';
const cuaGloballyEnabled = enableCua || cuaEnabledFlag;

const useBrowserbaseForCua = (process.env.USE_BROWSERBASE_FOR_CUA || 'false').toLowerCase() === 'true';

// дешёвая LLM
const llmApiKey = process.env.LLM_API_KEY || '';
const llmModel = process.env.LLM_MODEL || 'gpt-3.5-turbo';
const llmBaseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1';

// Browserbase / CUA
const browserbaseApiKey = process.env.BROWSERBASE_API_KEY || '';
const browserbaseProjectId = process.env.BROWSERBASE_PROJECT_ID || '';
const cuaApiKey = process.env.CUA_API_KEY || '';
const cuaModel = process.env.CUA_MODEL || '';
const cuaBaseUrl = process.env.CUA_BASE_URL || '';
const cuaMaxSteps = Number(process.env.CUA_MAX_STEPS || 12);
const cuaMaxTokens = Number(process.env.CUA_MAX_TOKENS || 4000);

module.exports = {
  port,
  enableCua,
  cuaEnabledFlag,
  cuaGloballyEnabled,
  useBrowserbaseForCua,
  llmApiKey,
  llmModel,
  llmBaseUrl,
  browserbaseApiKey,
  browserbaseProjectId,
  cuaApiKey,
  cuaModel,
  cuaBaseUrl,
  cuaMaxSteps,
  cuaMaxTokens,
};
