// FILE: link_analyzer/src/services/cheapParser.js
const axios = require('axios');
const cheerio = require('cheerio');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const { fetchGoogleDoc } = require('./googleDocParser');
const logger = require('../utils/logger');

async function cheapParse(rawUrl, contentType) {
  const { parsed, limitations, errors } = await cheapParseWithSignals(rawUrl, contentType);
  return { parsed, limitations, errors };
}

async function cheapParseWithSignals(rawUrl, contentType) {
  const limitations = [];
  const errors = [];

  if (contentType === 'google_doc') {
    try {
      const content = await fetchGoogleDoc(rawUrl);
      const parsedPage = new ParsedPage({ url: rawUrl, content });
      const textLength = content ? content.length : 0;
      return {
        parsed: parsedPage,
        limitations,
        errors,
        signals: {
          htmlLength: textLength,
          textLength,
          canvasCount: 0,
          svgCount: 0,
          iframeCount: 0,
          imgCount: 0,
          linkCount: 0,
          inputCount: 0,
        },
      };
    } catch (error) {
      errors.push('Failed to fetch Google Doc');
      logger.error(`Google Doc parsing failed: ${error.message}`);
      return {
        parsed: null,
        limitations,
        errors,
        signals: {
          htmlLength: 0,
          textLength: 0,
          canvasCount: 0,
          svgCount: 0,
          iframeCount: 0,
          imgCount: 0,
          linkCount: 0,
          inputCount: 0,
        },
      };
    }
  }

  try {
    const response = await axios.get(rawUrl, {
      timeout: 10000,
      maxRedirects: 5,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
      },
    });
    const html = response.data;
    const htmlLength = typeof html === 'string' ? html.length : 0;
    const meta = extractTextFromHtml(html);
    const $ = cheerio.load(html);
    const parsed = new ParsedPage({
      url: rawUrl,
      title: meta.title,
      description: meta.description,
      content: meta.content,
      statusCode: response.status,
      contentLength: Number(response.headers['content-length']) || htmlLength || null,
    });

    const signals = {
      htmlLength,
      textLength: meta.content ? meta.content.length : 0,
      canvasCount: $('canvas').length,
      svgCount: $('svg').length,
      iframeCount: $('iframe').length,
      imgCount: $('img').length,
      linkCount: $('a').length,
      inputCount: $('input,button,select,textarea').length,
    };

    return { parsed, limitations, errors, signals };
  } catch (error) {
    logger.error(`Cheap parse failed for ${rawUrl}: ${error.message}`);
    errors.push('Cheap parser failed');
    if (error.response) {
      limitations.push(`HTTP status ${error.response.status}`);
    } else if (error.code === 'ECONNABORTED') {
      limitations.push('Request timeout');
    }
    return {
      parsed: null,
      limitations,
      errors,
      signals: {
        htmlLength: 0,
        textLength: 0,
        canvasCount: 0,
        svgCount: 0,
        iframeCount: 0,
        imgCount: 0,
        linkCount: 0,
        inputCount: 0,
      },
    };
  }
}

module.exports = { cheapParse, cheapParseWithSignals };
