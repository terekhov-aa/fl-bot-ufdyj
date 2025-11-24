const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const config = require('../config');
const logger = require('../utils/logger');

async function analyzeWithCua(rawUrl, contentType, limitations) {
  if (!config.enableCua) {
    limitations.push('CUA disabled');
    return { parsed: null, used: false };
  }
  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    const html = await page.content();
    const meta = extractTextFromHtml(html);
    const parsed = new ParsedPage({ url: rawUrl, title: meta.title, description: meta.description, content: meta.content });
    return { parsed, used: true };
  } catch (error) {
    logger.error(`CUA analysis failed: ${error.message}`);
    limitations.push('CUA failed');
    return { parsed: null, used: true };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

module.exports = { analyzeWithCua };
