// FILE: link_analyzer/src/services/cuaService.js
const axios = require('axios');
const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const ProjectInfo = require('../models/ProjectInfo');
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

  try {
    const hasBrowserbaseConfig =
      config.useBrowserbaseForCua &&
      config.browserbaseApiKey &&
      config.browserbaseProjectId &&
      config.cuaBaseUrl &&
      config.cuaModel &&
      config.cuaApiKey;

    if (hasBrowserbaseConfig) {
      try {
        const response = await axios.post(
          `${config.cuaBaseUrl}/analyze`,
          {
            url,
            model: config.cuaModel,
            maxSteps: config.cuaMaxSteps,
            maxTokens: config.cuaMaxTokens,
            browserbase: {
              apiKey: config.browserbaseApiKey,
              projectId: config.browserbaseProjectId,
            },
            signals: options.signals || {},
          },
          {
            headers: {
              Authorization: `Bearer ${config.cuaApiKey}`,
              'Content-Type': 'application/json',
            },
            timeout: 30000,
          }
        );

        const data = response.data || {};
        if (data.projectInfo) {
          const mappedProject = new ProjectInfo();
          Object.assign(mappedProject, data.projectInfo);
          projectInfoFromCUA = mappedProject;
        }
        projectInfoText = data.textSummary || data.rawText || null;
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
        if (!data.projectInfo && !data.rawText) {
          limitations.push('Browserbase/Stagehand CUA returned no data');
        }
      } catch (err) {
        errors.push(`Browserbase/Stagehand CUA error: ${err.message}`);
        limitations.push('Browserbase/Stagehand CUA integration issue, falling back to Puppeteer');
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
  } catch (error) {
    errors.push(`CUA error: ${error.message || String(error)}`);
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
