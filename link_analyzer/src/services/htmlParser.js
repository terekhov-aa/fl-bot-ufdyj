const cheerio = require('cheerio');
const { normalizeWhitespace } = require('../utils/textUtils');

function extractTextFromHtml(html) {
  const $ = cheerio.load(html);
  $('script, style, noscript').remove();
  const title = normalizeWhitespace($('title').first().text());
  const description = normalizeWhitespace($('meta[name="description"]').attr('content') || '');
  const headings = $('h1,h2,h3')
    .toArray()
    .map((el) => normalizeWhitespace($(el).text()))
    .filter(Boolean);
  const bodyText = normalizeWhitespace($('body').text());
  const content = [title, description, headings.join(' '), bodyText].filter(Boolean).join('\n');
  return { title, description, content };
}

module.exports = { extractTextFromHtml };
