const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParse } = require('./cheapParser');
const { extractProjectInfoFromText } = require('./llmClient');
const { analyzeWithCua } = require('./cuaService');
const config = require('../config');
const logger = require('../utils/logger');

const MIN_CONTENT_LENGTH_FOR_LLM = 300;
const COMPLEX_CONTENT_TYPES = ['figma', 'miro', 'stitch', 'video'];

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
    }
  }

  const shouldUseCua =
    config.cuaEnabled &&
    !result.projectInfo &&
    (!result.parsed ||
      !result.parsed.content ||
      result.parsed.content.length < MIN_CONTENT_LENGTH_FOR_LLM ||
      COMPLEX_CONTENT_TYPES.includes(result.contentType) ||
      result.limitations.includes('doc_viewer') ||
      result.limitations.includes('design_link_limited') ||
      result.limitations.includes('auth_required_or_limited_access'));

  if (shouldUseCua) {
    logger.info(`Switching to CUA agent for ${rawUrl} (type=${result.contentType})`);
    const cuaOutcome = await analyzeWithCua(rawUrl, contentType, result.limitations);
    if (cuaOutcome.parsed && (!result.parsed || cuaOutcome.parsed.content.length > (result.parsed?.content?.length || 0))) {
      result.parsed = cuaOutcome.parsed;
    }

    if (cuaOutcome.projectInfo) {
      result.projectInfo = cuaOutcome.projectInfo;
      result.analysisMode = 'cua_agent';
    } else if (cuaOutcome.parsed && cuaOutcome.parsed.content) {
      const projectInfoFromCua = await extractProjectInfoFromText(cuaOutcome.parsed.content);
      if (projectInfoFromCua) {
        result.projectInfo = projectInfoFromCua;
        result.analysisMode = 'cua_agent';
      }
    }

    if (!result.projectInfo && (!result.analysisMode || result.analysisMode === 'cheap_parser')) {
      result.analysisMode = 'cheap_parser_cua_failed';
    }
  }

  if (!result.parsed && !result.projectInfo) {
    result.success = false;
    result.errors.push('Parsing failed');
  }

  logger.info(`Analysis finished for ${rawUrl} with mode ${result.analysisMode}`);
  return result;
}

module.exports = { analyzeUrl };
