class ParsedPage {
  constructor({
    url,
    title = '',
    description = '',
    content = '',
    statusCode = null,
    contentLength = null,
    htmlLength = null,
    textLength = null,
    textDensity = null,
    canvasCount = 0,
    svgCount = 0,
    inputControlCount = 0,
    suspectedCanvasApp = false,
  }) {
    this.url = url;
    this.title = title;
    this.description = description;
    this.content = content;
    this.statusCode = statusCode;
    this.contentLength = contentLength;
    this.htmlLength = htmlLength;
    this.textLength = textLength;
    this.textDensity = textDensity;
    this.canvasCount = canvasCount;
    this.svgCount = svgCount;
    this.inputControlCount = inputControlCount;
    this.suspectedCanvasApp = suspectedCanvasApp;
    this.textPreview = content ? content.slice(0, 500) : '';
  }
}

module.exports = ParsedPage;
