class ParsedPage {
  constructor({ url, title = '', description = '', content = '', statusCode = null, contentLength = null }) {
    this.url = url;
    this.title = title;
    this.description = description;
    this.content = content;
    this.statusCode = statusCode;
    this.contentLength = contentLength;
    this.textPreview = content ? content.slice(0, 500) : '';
  }
}

module.exports = ParsedPage;
