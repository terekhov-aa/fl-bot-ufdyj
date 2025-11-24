const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const ParsedPage = require('../models/ParsedPage');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParse } = require('./cheapParser');
const { extractProjectInfoFromText } = require('./llmClient');
const { analyzeWithCua } = require('./cuaService');
const { normalizeWhitespace, truncateText } = require('../utils/textUtils');
const logger = require('../utils/logger');

function mergeParsedPages(primary, secondary) {
  if (!primary && !secondary) return null;
  if (primary && !secondary) return primary;
  if (!primary && secondary) return secondary;

  const mergedContent = truncateText(
    normalizeWhitespace([primary.content, secondary.content].filter(Boolean).join('\n\n')),
    15000,
  );

  return new ParsedPage({
    url: primary.url || secondary.url,
    title: primary.title || secondary.title,
    description: primary.description || secondary.description,
    content: mergedContent,
    statusCode: primary.statusCode || secondary.statusCode,
    contentLength: primary.contentLength || secondary.contentLength,
    textPreview: primary.textPreview || secondary.textPreview,
  });
}

async function analyzeUrl(rawUrl) {
  const contentType = detectContentType(rawUrl);
  const result = new LinkAnalysisResult();
  result.contentType = contentType;

  const { parsed, limitations, errors } = await cheapParse(rawUrl, contentType);
  result.parsed = parsed;
  result.limitations = limitations;
  result.errors = errors;

  if (contentType === 'design_tool') {
    if (!result.limitations.includes('design_tool_dynamic_content')) {
      result.limitations.push('design_tool_dynamic_content');
    }

    const cuaOutcome = await analyzeWithCua(rawUrl, contentType, result.limitations);
    result.parsed = mergeParsedPages(cuaOutcome.parsed, result.parsed);
    result.analysisMode = cuaOutcome.used ? 'design_tool_cua' : 'design_tool';

    if (result.parsed && result.parsed.content) {
      const projectInfo = await extractProjectInfoFromText(result.parsed.content);
      if (projectInfo) {
        result.projectInfo = projectInfo;
      }
    }

    if (!result.parsed) {
      result.success = false;
      result.errors.push('Parsing failed');
    }

    logger.info(
      `Analysis finished for ${rawUrl} (type=${contentType}) with mode ${result.analysisMode}; content length=${result.parsed?.content?.length || 0}`,
    );
    return result;
  }

  if (parsed && parsed.content) {
    const projectInfo = await extractProjectInfoFromText(parsed.content);
    if (projectInfo) {
      result.projectInfo = projectInfo;
      result.analysisMode = 'cheap_parser+llm';
      logger.info(`Analysis finished for ${rawUrl} with mode ${result.analysisMode}`);
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
