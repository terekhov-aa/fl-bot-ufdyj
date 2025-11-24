const axios = require('axios');
const config = require('../config');
const ProjectInfo = require('../models/ProjectInfo');
const { truncateText } = require('../utils/textUtils');
const logger = require('../utils/logger');

async function extractProjectInfoFromText(text) {
  if (!config.llmApiKey) {
    logger.warn('LLM_API_KEY is not configured; skipping LLM extraction');
    return null;
  }
  const trimmed = truncateText(text, 8000);
  const payload = {
    model: config.llmModel,
    messages: [
      {
        role: 'system',
        content:
          'You are an assistant that extracts structured project details from arbitrary text. Respond with JSON matching the requested schema.',
      },
      {
        role: 'user',
        content:
          'Extract project info: projectType, summary, targetAudience, mainFlows (array), mainFeatures (array), techStackGuess (array), complexity (low/medium/high/unknown), risks (array), tasksForFreelancer (array) from the following text. Return strict JSON.',
      },
      { role: 'user', content: trimmed },
    ],
    response_format: { type: 'json_object' },
  };

  try {
    const response = await axios.post(`${config.llmBaseUrl}/chat/completions`, payload, {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.llmApiKey}`,
      },
      timeout: 20000,
    });
    const content = response.data.choices?.[0]?.message?.content;
    if (!content) return null;
    const parsed = JSON.parse(content);
    const project = new ProjectInfo();
    Object.assign(project, parsed);
    return project;
  } catch (error) {
    logger.error(`LLM extraction failed: ${error.message}`);
    return null;
  }
}

module.exports = { extractProjectInfoFromText };
