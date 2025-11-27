// FILE: link_analyzer/src/services/googleDocParser.js
const axios = require('axios');
const cheerio = require('cheerio');
const logger = require('../utils/logger');

async function fetchGoogleDoc(rawUrl) {
  try {
    const response = await axios.get(rawUrl, { timeout: 15000 });
    const html = response.data;
    const $ = cheerio.load(html);
    $('script, style, noscript').remove();
    return $('body').text().replace(/\s+/g, ' ').trim();
  } catch (error) {
    logger.error(`Failed to fetch Google Doc: ${error.message}`);
    throw error;
  }
}

module.exports = {
  fetchGoogleDoc,
};
