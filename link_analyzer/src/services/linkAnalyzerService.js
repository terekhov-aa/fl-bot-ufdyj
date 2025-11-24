const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParse } = require('./cheapParser');
const { extractProjectInfoFromText } = require('./llmClient');
const { analyzeWithCua } = require('./cuaService');
const logger = require('../utils/logger');

async function analyzeUrl(rawUrl) {
  const contentType = detectContentType(rawUrl);
  const result = new LinkAnalysisResult();
  result.contentType = contentType;

  const { parsed, limitations, errors } = await cheapParse(rawUrl, contentType);
  result.parsed = parsed;
  result.limitations = limitations;
  result.errors = errors;

  if (parsed && parsed.content) {
    const projectInfo = await extractProjectInfoFromText(parsed.content);
    if (projectInfo) {
      result.projectInfo = projectInfo;
      result.analysisMode = 'cheap_parser+llm';
      return result;
    }
  }

  const cuaOutcome = await analyzeWithCua(rawUrl, contentType, result.limitations);
  if (cuaOutcome.parsed) {
    result.parsed = cuaOutcome.parsed;
    result.analysisMode = 'cua';
    if (cuaOutcome.parsed.content) {
      const projectInfo = await extractProjectInfoFromText(cuaOutcome.parsed.content);
      if (projectInfo) {
        result.projectInfo = projectInfo;
      }
    }
  }

  if (!result.parsed) {
    result.success = false;
    result.errors.push('Parsing failed');
  }

  logger.info(`Analysis finished for ${rawUrl} with mode ${result.analysisMode}`);
  return result;
}

module.exports = { analyzeUrl };
