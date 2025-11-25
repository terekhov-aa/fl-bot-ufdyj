// FILE: link_analyzer/src/services/contentTypeDetector.js
function detectContentType(url) {
  if (!url) return 'web_page';
  const lower = url.toLowerCase();
  if (lower.includes('docs.google.com/document')) {
    return 'google_doc';
  }
  return 'web_page';
}

module.exports = {
  detectContentType,
};
