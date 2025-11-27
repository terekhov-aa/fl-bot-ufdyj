// FILE: link_analyzer/src/models/LinkAnalysisResult.js
class LinkAnalysisResult {
  constructor() {
    this.success = true;
    this.contentType = 'web_page';
    this.analysisMode = 'cheap_parser';
    this.parsed = null;
    this.projectInfo = null;
    this.limitations = [];
    this.errors = [];
  }
}

module.exports = LinkAnalysisResult;
