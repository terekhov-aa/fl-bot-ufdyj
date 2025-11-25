// FILE: link_analyzer/src/services/cuaService.js
const { Stagehand } = require('@browserbasehq/stagehand');
const ParsedPage = require('../models/ParsedPage');
const config = require('../config');
const logger = require('../utils/logger');

/**
 * @param {string} url
 * @param {object} options
 * @param {string} [options.contentType]
 * @param {object} [options.signals]
 */
async function runCUAForProjectInfo(url, options = {}) {
  const limitations = [];
  const errors = [];

  if (!config.cuaGloballyEnabled) {
    limitations.push('CUA is disabled via CUA_ENABLED/ENABLE_CUA');
    return { parsedPageFromCUA: null, projectInfoFromCUA: null, projectInfoText: null, limitations, errors };
  }

  let parsedPageFromCUA = null;
  let projectInfoFromCUA = null;
  let projectInfoText = null;
  let stagehand;

  if (!config.browserbaseApiKey || !config.browserbaseProjectId) {
    limitations.push('Browserbase credentials missing for CUA');
    return { parsedPageFromCUA, projectInfoFromCUA, projectInfoText, limitations, errors };
  }

  try {
    logger.info('Launching Stagehand CUA', { model: config.cuaModel, signals: options.signals });

    stagehand = new Stagehand({
      env: 'BROWSERBASE',
      apiKey: config.browserbaseApiKey,
      projectId: config.browserbaseProjectId,
    });

    await stagehand.init();

    const page = stagehand.page || (stagehand.context && stagehand.context.pages()[0]);

    if (!page) {
      throw new Error('Stagehand page not available');
    }

    await page.goto(url, { waitUntil: 'networkidle' });

    const agent = stagehand.agent({
      cua: true,
      model: config.cuaModel || 'google/gemini-2.5-computer-use-preview-10-2025',
      systemPrompt:
        'You are a helpful assistant that can control a web browser and read product/project pages. Focus on extracting as much textual context as possible for a freelancer who will build or maintain this project.',
      maxSteps: config.cuaMaxSteps,
      maxOutputTokens: config.cuaMaxTokens,
    });

    const instruction =
      'You are currently on a page that describes some product or project. Carefully scroll and inspect the page. Then return a long, dense plain-text summary of everything that is important: what this project is, target audience, main flows, main features, tech stack hints, complexity, risks, and tasks for a freelancer. Do not return JSON, only a single plain-text block.';

    const agentResult = await agent.execute(instruction);

    const text =
      typeof agentResult === 'string'
        ? agentResult
        : agentResult?.message || agentResult?.output || '';

    if (!text) {
      limitations.push('CUA agent returned empty message');
    }

    if (agentResult && agentResult.success === false) {
      limitations.push('CUA agent reported unsuccessful execution');
    }

    if (text) {
      parsedPageFromCUA = new ParsedPage({
        url,
        title: (await page.title().catch(() => '')) || '',
        description: '',
        content: text,
        statusCode: 200,
        contentLength: text.length,
      });
      projectInfoText = text;
    }
  } catch (err) {
    limitations.push('Stagehand CUA failed');
    errors.push(`CUA error: ${err.message}`);
    logger.error(`CUA error: ${err.message}`);
  } finally {
    if (stagehand) {
      try {
        await stagehand.close();
      } catch (closeError) {
        logger.error(`Failed to close Stagehand: ${closeError.message}`);
      }
    }
  }

  return {
    parsedPageFromCUA: parsedPageFromCUA || null,
    projectInfoFromCUA: projectInfoFromCUA || null,
    projectInfoText: projectInfoText || null,
    limitations,
    errors,
  };
}

module.exports = {
  runCUAForProjectInfo,
};
