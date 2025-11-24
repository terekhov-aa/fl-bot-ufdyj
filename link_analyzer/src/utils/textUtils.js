function normalizeWhitespace(text) {
  if (!text) return '';
  return text.replace(/\s+/g, ' ').trim();
}

function truncateText(text, maxLength) {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

module.exports = {
  normalizeWhitespace,
  truncateText,
};
