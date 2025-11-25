// FILE: link_analyzer/src/config.js
const port = parseInt(process.env.PORT || '3000', 10);

// флаги CUA
const enableCua = (process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const cuaEnabledFlag = (process.env.CUA_ENABLED || '').toLowerCase() === 'true';
const cuaGloballyEnabled = enableCua || cuaEnabledFlag;

// дешёвая LLM
const llmApiKey = process.env.LLM_API_KEY || '';
const llmModel = process.env.LLM_MODEL || 'gpt-3.5-turbo';
const llmBaseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1';

// Browserbase / CUA
const browserbaseApiKey = process.env.BROWSERBASE_API_KEY || '';
const browserbaseProjectId = process.env.BROWSERBASE_PROJECT_ID || '';
const cuaModel = process.env.CUA_MODEL || 'google/gemini-2.5-computer-use-preview-10-2025';
const cuaMaxSteps = Number(process.env.CUA_MAX_STEPS || 16);
const cuaMaxTokens = Number(process.env.CUA_MAX_TOKENS || 4000);

module.exports = {
  port,
  enableCua,
  cuaEnabledFlag,
  cuaGloballyEnabled,
  llmApiKey,
  llmModel,
  llmBaseUrl,
  browserbaseApiKey,
  browserbaseProjectId,
  cuaModel,
  cuaMaxSteps,
  cuaMaxTokens,
};
