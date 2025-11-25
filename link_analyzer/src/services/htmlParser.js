// FILE: link_analyzer/src/services/htmlParser.js
const cheerio = require('cheerio');

function extractTextFromHtml(html) {
  if (!html) {
    return { title: '', description: '', content: '' };
  }
  const $ = cheerio.load(html);
  const title = ($('title').first().text() || '').trim();
  const description = ($('meta[name="description"]').attr('content') || '').trim();

  $('script, style, noscript').remove();
  const content = $('body').text().replace(/\s+/g, ' ').trim();

  return { title, description, content };
}

module.exports = {
  extractTextFromHtml,
};
