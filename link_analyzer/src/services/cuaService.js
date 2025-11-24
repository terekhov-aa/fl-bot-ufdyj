const puppeteer = require('puppeteer');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const { normalizeWhitespace, truncateText } = require('../utils/textUtils');
const config = require('../config');
const logger = require('../utils/logger');

async function analyzeWithCua(rawUrl, contentType, limitations = []) {
  if (!config.enableCua) {
    limitations.push('cua_disabled');
    return { parsed: null, used: false };
  }
  let browser;
  try {
    browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page = await browser.newPage();
    await page.goto(rawUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForTimeout(1000);
    await page.evaluate(() => {
      try {
        window.scrollTo(0, document.body ? document.body.scrollHeight / 2 : 0);
      } catch (e) {
        // ignore scroll errors
      }
    });
    await page.waitForTimeout(1000);

    const pageText = await page.evaluate(() => {
      const title = document.title || '';
      const bodyText = document.body ? document.body.innerText || '' : '';
      const sidebarText = Array.from(document.querySelectorAll('[class*="sidebar"], [class*="panel"], nav, aside'))
        .map((el) => el.innerText || '')
        .join('\n');
      return { title, bodyText, sidebarText };
    });

    const html = await page.content();
    const htmlMeta = extractTextFromHtml(html);

    const combinedContent = truncateText(
      normalizeWhitespace(
        [pageText.bodyText, pageText.sidebarText, htmlMeta.content].filter(Boolean).join('\n'),
      ),
      15000,
    );

    const descriptionCandidate = normalizeWhitespace(pageText.bodyText || '') || htmlMeta.description || '';

    const parsed = new ParsedPage({
      url: rawUrl,
      title: normalizeWhitespace(pageText.title) || htmlMeta.title,
      description: truncateText(descriptionCandidate || htmlMeta.description || '', 400),
      content: combinedContent,
    });

    logger.info(
      `CUA parsed content for ${rawUrl} (type=${contentType}) length=${parsed.content ? parsed.content.length : 0}`,
    );
    return { parsed, used: true };
  } catch (error) {
    logger.error(`CUA analysis failed: ${error.message}`);
    limitations.push('cua_failed');
    return { parsed: null, used: true };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

module.exports = { analyzeWithCua };
