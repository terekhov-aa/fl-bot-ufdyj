function detectContentType(rawUrl) {
  const url = rawUrl.toLowerCase();
  if (url.includes('docs.google.com/document')) return 'google_doc';
  if (url.includes('notion.so')) return 'notion';
  if (url.includes('atlassian.net') || url.includes('confluence')) return 'confluence';
  if (url.includes('figma.com')) return 'figma';
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
  if (url.includes('github.com')) return 'github';
  return 'web_page';
}

module.exports = { detectContentType };
