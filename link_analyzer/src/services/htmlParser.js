const cheerio = require('cheerio');
const { normalizeWhitespace } = require('../utils/textUtils');

function detectWebglHints(html) {
  const lower = html.toLowerCase();
  const hints = ['webgl', 'three.js', 'threejs', 'pixi.js', 'pixijs', 'gl_position', 'gl_fragcolor', 'shader', 'canvas', 'babylon.js', 'webgpu'];
  return hints.some((hint) => lower.includes(hint));
}

function extractTextFromHtml(html) {
  const htmlLength = html ? html.length : 0;
  const $ = cheerio.load(html || '');
  $('script, style, noscript').remove();

  const title = normalizeWhitespace($('title').first().text());
  const description = normalizeWhitespace($('meta[name="description"]').attr('content') || '');
  const headings = $('h1,h2,h3')
    .toArray()
    .map((el) => normalizeWhitespace($(el).text()))
    .filter(Boolean);
  const bodyText = normalizeWhitespace($('body').text());
  const content = [title, description, headings.join(' '), bodyText].filter(Boolean).join('\n');

  const textLength = content.length;
  const textDensity = htmlLength > 0 ? Math.min(1, Math.max(0, textLength / htmlLength)) : null;
  const canvasCount = $('canvas').length;
  const svgCount = $('svg').length;
  const inputControlCount = $('button, input, textarea, select, [role="button"], [contenteditable="true"]').length;
  const possibleWebglHints = detectWebglHints(html || '');

  const suspectedCanvasApp =
    canvasCount > 0 ||
    (textDensity !== null && textDensity < 0.01 && htmlLength > 50000) ||
    (canvasCount === 0 && svgCount > 10 && textDensity !== null && textDensity < 0.02) ||
    possibleWebglHints;

  return {
    title,
    description,
    content,
    htmlLength,
    textLength,
    textDensity,
    canvasCount,
    svgCount,
    inputControlCount,
    suspectedCanvasApp,
  };
}

module.exports = { extractTextFromHtml };
