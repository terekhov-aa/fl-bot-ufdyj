// FILE: link_analyzer/src/services/cuaService.js
const { Stagehand } = require('@browserbasehq/stagehand');
const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const logger = require('../utils/logger');

async function renderWithPuppeteer(rawUrl) {
  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    const html = await page.content();
    return html;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function analyzeWithCua(rawUrl, contentType, limitations = []) {
  if (!config.cuaGloballyEnabled) {
    limitations.push('CUA disabled');
    return { parsed: null, used: false };
  }
  try {
    const html = await renderWithPuppeteer(rawUrl);
    const meta = extractTextFromHtml(html);
    const parsed = new ParsedPage({ url: rawUrl, title: meta.title, description: meta.description, content: meta.content });
    return { parsed, used: true };
  } catch (error) {
    logger.error(`CUA analysis failed: ${error.message}`);
    limitations.push('CUA failed');
    return { parsed: null, used: true };
  }
}

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

  const hasBrowserbaseConfig =
    config.useBrowserbaseForCua &&
    config.browserbaseApiKey &&
    config.browserbaseProjectId;

  if (hasBrowserbaseConfig) {
    try {
      const stagehand = new Stagehand({
        apiKey: config.browserbaseApiKey,
        projectId: config.browserbaseProjectId,
        model: config.cuaModel || config.llmModel,
      });

      const runResult = await stagehand.run({
        url,
        cua: true,
        maxSteps: config.cuaMaxSteps,
        maxTokens: config.cuaMaxTokens,
        metadata: options.signals || {},
        instructions: `
          Ты агент, который анализирует продукт/проект по веб-интерфейсу.
          1. Прокликай и проскроль страницу, чтобы понять, что это за продукт.
          2. Сформируй JSON со следующей структурой:
          {
            "projectInfo": {
              "projectType": string,
              "summary": string,
              "targetAudience": string,
              "mainFlows": string[],
              "mainFeatures": string[],
              "techStackGuess": string[],
              "complexity": "low" | "medium" | "high" | "unknown",
              "risks": string[],
              "tasksForFreelancer": string[]
            },
            "textSummary": string,
            "rawText": string,
            "title": string,
            "description": string
          }
          Верни ТОЛЬКО JSON без лишнего текста.
        `,
      });

      const outputText = runResult?.outputText || runResult?.output || runResult?.text || '';
      let data = {};
      if (outputText && typeof outputText === 'string') {
        try {
          data = JSON.parse(outputText);
        } catch (e) {
          limitations.push('Stagehand returned non-JSON output');
          errors.push(`Browserbase CUA parse error: ${e.message}`);
        }
      }

      if (data.rawText) {
        parsedPageFromCUA = new ParsedPage({
          url,
          title: data.title || '',
          description: data.description || '',
          content: data.rawText,
          statusCode: 200,
          contentLength: data.rawText.length,
        });
      }

      if (data.textSummary) {
        projectInfoText = data.textSummary;
      }

      if (!data.rawText && !data.textSummary) {
        limitations.push('Browserbase/Stagehand CUA returned no usable data');
      }
    } catch (err) {
      limitations.push('Browserbase/Stagehand CUA failed');
      errors.push(`Browserbase CUA error: ${err.message}`);
    }
  } else {
    limitations.push('Browserbase CUA not fully configured, using Puppeteer fallback');
  }

  if (!parsedPageFromCUA && config.cuaGloballyEnabled) {
    try {
      const html = await renderWithPuppeteer(url);
      const meta = extractTextFromHtml(html);
      parsedPageFromCUA = new ParsedPage({
        url,
        title: meta.title,
        description: meta.description,
        content: meta.content,
      });
    } catch (err) {
      limitations.push('Puppeteer fallback failed');
      errors.push(`CUA error: ${err.message}`);
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
  analyzeWithCua,
  runCUAForProjectInfo,
};
