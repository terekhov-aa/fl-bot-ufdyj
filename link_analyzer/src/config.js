const port = parseInt(process.env.PORT || '3000', 10);
const enableCua = (process.env.ENABLE_CUA || 'true').toLowerCase() === 'true';
const llmApiKey = process.env.LLM_API_KEY || '';
const llmModel = process.env.LLM_MODEL || 'gpt-3.5-turbo';
const llmBaseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1';

module.exports = {
  port,
  enableCua,
  llmApiKey,
  llmModel,
  llmBaseUrl,
};
