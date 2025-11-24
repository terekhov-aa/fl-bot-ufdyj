const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const logger = require('../utils/logger');

async function runPuppeteerFallback(rawUrl) {
  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    await page.waitForTimeout(1000);
    const html = await page.content();
    const meta = extractTextFromHtml(html);
    return new ParsedPage({ url: rawUrl, title: meta.title, description: meta.description, content: meta.content });
  } catch (error) {
    logger.error(`CUA puppeteer fallback failed: ${error.message}`);
    return null;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function runCUAForProjectInfo(rawUrl, options = {}) {
  const limitations = [];
  const errors = [];

  if (!config.enableCua) {
    limitations.push('CUA disabled');
    return { parsedPageFromCUA: null, projectInfoFromCUA: null, projectInfoText: null, limitations, errors };
  }

  let parsedPageFromCUA = null;
  let projectInfoFromCUA = null;
  let projectInfoText = null;

  // TODO: Integrate with Browserbase/Stagehand when credentials are available.
  if (config.cuaBaseUrl && config.cuaApiKey) {
    limitations.push('External CUA endpoint configured but not implemented; using puppeteer fallback');
  }

  parsedPageFromCUA = await runPuppeteerFallback(rawUrl);
  if (!parsedPageFromCUA) {
    errors.push('CUA failed');
  } else {
    projectInfoText = parsedPageFromCUA.content || null;
  }

  return { parsedPageFromCUA, projectInfoFromCUA, projectInfoText, limitations, errors };
}

async function analyzeWithCua(rawUrl, contentType, limitations) {
  const cuaResult = await runCUAForProjectInfo(rawUrl, { contentType });
  if (cuaResult.limitations?.length) {
    limitations.push(...cuaResult.limitations);
  }
  return { parsed: cuaResult.parsedPageFromCUA, used: !!cuaResult.parsedPageFromCUA };
}

module.exports = { analyzeWithCua, runCUAForProjectInfo };
