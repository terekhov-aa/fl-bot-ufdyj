const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParse } = require('./cheapParser');
const { extractProjectInfoFromText } = require('./llmClient');
const { analyzeWithCua } = require('./cuaService');
const logger = require('../utils/logger');
const config = require('../config');

const MIN_TEXT_FOR_LLM = 300;

function shouldUseCuaForParsed(result) {
  const parsed = result.parsed;
  if (!parsed) return true;

  const hasLittleText = !parsed.content || parsed.content.length < MIN_TEXT_FOR_LLM;
  const isLowDensity = parsed.textDensity !== null && parsed.textDensity < 0.01;
  const isLargeHtml = parsed.htmlLength !== null && parsed.htmlLength > 50000;
  const isCanvasHeavy = parsed.canvasCount > 0 || parsed.suspectedCanvasApp === true;
  const hasViewerLimitations =
    result.limitations.includes('doc_viewer') || result.limitations.includes('design_link_limited');

  return (
    (!result.projectInfo && hasLittleText) ||
    isCanvasHeavy ||
    (isLowDensity && isLargeHtml) ||
    hasViewerLimitations
  );
}

async function analyzeUrl(rawUrl) {
  const contentType = detectContentType(rawUrl);
  const result = new LinkAnalysisResult();
  result.contentType = contentType;
  result.analysisMode = 'cheap_parser';

  const { parsed, limitations, errors } = await cheapParse(rawUrl, contentType);
  result.parsed = parsed;
  result.limitations = limitations;
  result.errors = errors;

  if (parsed && parsed.content) {
    const projectInfo = await extractProjectInfoFromText(parsed.content);
    if (projectInfo) {
      result.projectInfo = projectInfo;
      result.analysisMode = 'cheap_parser+llm';
      logger.info(`Analysis finished for ${rawUrl} with mode ${result.analysisMode}`);
      return result;
    }
  }

  const shouldUseCua =
    config.cuaEnabled &&
    shouldUseCuaForParsed(result) &&
    !result.limitations.includes('auth_required') &&
    !result.limitations.includes('auth_required_or_limited_access');

  if (shouldUseCua) {
    logger.info(`Switching to CUA for ${rawUrl} ...`);
    const cuaOutcome = await analyzeWithCua(rawUrl, contentType, result.limitations);
    if (cuaOutcome.parsed) {
      result.parsed = cuaOutcome.parsed;
    }
    if (cuaOutcome.projectInfo) {
      result.projectInfo = cuaOutcome.projectInfo;
      result.analysisMode = 'cua_agent';
    } else if (cuaOutcome.parsed && cuaOutcome.parsed.content) {
      const projectInfo = await extractProjectInfoFromText(cuaOutcome.parsed.content);
      if (projectInfo) {
        result.projectInfo = projectInfo;
        result.analysisMode = 'cua_agent';
      }
    }

    if (!result.projectInfo && result.analysisMode === 'cheap_parser') {
      result.analysisMode = 'cheap_parser_cua_failed';
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
