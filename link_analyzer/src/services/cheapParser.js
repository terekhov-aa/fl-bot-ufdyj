const axios = require('axios');
const ParsedPage = require('../models/ParsedPage');
const { extractTextFromHtml } = require('./htmlParser');
const { fetchGoogleDoc } = require('./googleDocParser');
const logger = require('../utils/logger');

async function cheapParse(rawUrl, contentType) {
  const limitations = [];
  const errors = [];
  if (contentType === 'google_doc') {
    try {
      const content = await fetchGoogleDoc(rawUrl);
      return { parsed: new ParsedPage({ url: rawUrl, content }), limitations, errors };
    } catch (error) {
      errors.push('Failed to fetch Google Doc');
      logger.error(`Google Doc parsing failed: ${error.message}`);
      return { parsed: null, limitations, errors };
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
    const meta = extractTextFromHtml(html);
    if (meta.textDensity !== null && meta.textDensity < 0.01) {
      limitations.push('low_text_density');
    }
    if (meta.suspectedCanvasApp) {
      limitations.push('likely_canvas_app');
    }

    const parsed = new ParsedPage({
      url: rawUrl,
      title: meta.title,
      description: meta.description,
      content: meta.content,
      statusCode: response.status,
      contentLength: Number(response.headers['content-length']) || null,
      htmlLength: meta.htmlLength,
      textLength: meta.textLength,
      textDensity: meta.textDensity,
      canvasCount: meta.canvasCount,
      svgCount: meta.svgCount,
      inputControlCount: meta.inputControlCount,
      suspectedCanvasApp: meta.suspectedCanvasApp,
    });
    return { parsed, limitations, errors };
  } catch (error) {
    logger.error(`Cheap parse failed for ${rawUrl}: ${error.message}`);
    errors.push('Cheap parser failed');
    if (error.response) {
      limitations.push(`HTTP status ${error.response.status}`);
    } else if (error.code === 'ECONNABORTED') {
      limitations.push('Request timeout');
    }
    return { parsed: null, limitations, errors };
  }
}

module.exports = { cheapParse };
