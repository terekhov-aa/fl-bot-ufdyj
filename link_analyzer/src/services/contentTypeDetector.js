const designToolPatterns = [
  'figma.com/design',
  'figma.com/file',
  'miro.com/app/board',
  'canva.com/design',
  'whimsical.com',
  'stitch.withgoogle.com/projects',
];

function detectContentType(rawUrl) {
  const url = rawUrl.toLowerCase();

  if (designToolPatterns.some((pattern) => url.includes(pattern))) return 'design_tool';
  if (url.includes('docs.google.com/document')) return 'google_doc';
  if (url.includes('notion.so')) return 'notion';
  if (url.includes('atlassian.net') || url.includes('confluence')) return 'confluence';
  if (url.includes('figma.com')) return 'design_tool';
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
  if (url.includes('github.com')) return 'github';
  return 'web_page';
}
module.exports = { detectContentType, designToolPatterns };
