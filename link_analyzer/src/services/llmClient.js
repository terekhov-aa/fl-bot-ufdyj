// FILE: link_analyzer/src/services/llmClient.js
const axios = require('axios');
const config = require('../config');
const ProjectInfo = require('../models/ProjectInfo');
const { truncateText } = require('../utils/textUtils');
const logger = require('../utils/logger');

async function extractProjectInfoFromText(text, options = {}) {
  const { url, contentType, llmConfig = {}, source } = options;
  const effectiveConfig = {
    apiKey: llmConfig.apiKey || config.llmApiKey,
    model: llmConfig.model || config.llmModel,
    baseUrl: llmConfig.baseUrl || config.llmBaseUrl,
  };

  if (!effectiveConfig.apiKey) {
    logger.warn('LLM_API_KEY is not configured; skipping LLM extraction');
    return null;
  }

  const trimmed = truncateText(text, 8000);
  const payload = {
    model: effectiveConfig.model,
    messages: [
      {
        role: 'system',
        content: 'You are an assistant that extracts structured project info for a freelancer.',
      },
      {
        role: 'user',
        content: `Context URL: ${url || 'unknown'}; ContentType: ${contentType || 'web_page'}; Source: ${
          source || 'cheap_parser'
        }. Text:\n${trimmed}`,
      },
    ],
    response_format: { type: 'json_object' },
  };

  try {
    const response = await axios.post(`${effectiveConfig.baseUrl}/chat/completions`, payload, {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${effectiveConfig.apiKey}`,
      },
      timeout: 20000,
    });

    const data = response.data;
    const choice = data.choices && data.choices[0];
    const content = choice && choice.message && choice.message.content;
    if (!content) {
      logger.warn('LLM returned empty content for project info');
      return null;
    }

    let parsed;
    try {
      parsed = JSON.parse(content);
    } catch (e) {
      logger.error(`Failed to parse LLM JSON: ${e.message}`);
      return null;
    }

    const projectInfo = new ProjectInfo();
    Object.assign(projectInfo, parsed);
    return projectInfo;
  } catch (error) {
    logger.error(`LLM request failed: ${error.message}`);
    return null;
  }
}

module.exports = {
  extractProjectInfoFromText,
};
