// FILE: link_analyzer/src/services/linkAnalyzerService.js
const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParseWithSignals } = require('./cheapParser');
const { extractProjectInfoFromText } = require('./llmClient');
const { runCUAForProjectInfo } = require('./cuaService');
const { decideAnalysisMode } = require('../heuristics/heuristicAnalyzer');
const config = require('../config');
const logger = require('../utils/logger');

async function analyzeUrl(rawUrl) {
  const contentType = detectContentType(rawUrl);
  const result = new LinkAnalysisResult();
  result.contentType = contentType;

  const { parsed, limitations: cheapLimitations, errors: cheapErrors, signals } = await cheapParseWithSignals(
    rawUrl,
    contentType
  );
  const limitations = [...(cheapLimitations || [])];
  const errors = [...(cheapErrors || [])];

  const parsedPage = parsed;
  let finalParsed = parsedPage;
  let projectInfo = null;
  let analysisMode = 'cheap_parser';

  const heuristicDecision = decideAnalysisMode(parsedPage, signals || {});
  const { mode, reasons, signals: signalsWithDensity } = heuristicDecision;

  if (reasons.includes('viewer_like_or_visual_editor')) {
    limitations.push('Heuristics: viewer-like page, CUA recommended');
  }

  const llmConfig = {
    apiKey: config.llmApiKey,
    model: config.llmModel,
    baseUrl: config.llmBaseUrl,
  };
  const cuaGloballyEnabled = config.cuaGloballyEnabled;

  if (mode === 'cheap_only') {
    analysisMode = 'cheap_parser';
    if (signalsWithDensity?.textLength < 300) {
      limitations.push('Heuristics: limited text, LLM not invoked');
    }
  } else if (mode === 'cheap_plus_llm') {
    analysisMode = 'cheap_parser+llm';
    if (parsedPage && parsedPage.content) {
      projectInfo = await extractProjectInfoFromText(parsedPage.content, {
        url: rawUrl,
        contentType,
        llmConfig,
      });
    }
  } else if (mode === 'need_cua') {
    analysisMode = 'cua';

    if (!cuaGloballyEnabled) {
      limitations.push('CUA mode requested by heuristics, but disabled via ENABLE_CUA/CUA_ENABLED');
      if (parsedPage && parsedPage.content && parsedPage.content.length > 0) {
        analysisMode = 'cheap_parser+llm_fallback';
        projectInfo = await extractProjectInfoFromText(parsedPage.content, {
          url: rawUrl,
          contentType,
          llmConfig,
        });
      }
    } else {
      const cuaResult = await runCUAForProjectInfo(rawUrl, { contentType, signals: signalsWithDensity });
      if (cuaResult?.limitations?.length) limitations.push(...cuaResult.limitations);
      if (cuaResult?.errors?.length) errors.push(...cuaResult.errors);

      if (cuaResult?.parsedPageFromCUA && (cuaResult.parsedPageFromCUA.content?.length || 0) > (parsedPage?.content?.length || 0)) {
        finalParsed = cuaResult.parsedPageFromCUA;
      }

      if (cuaResult?.projectInfoFromCUA) {
        projectInfo = cuaResult.projectInfoFromCUA;
        analysisMode = 'cua_direct_project_info';
      } else if (cuaResult?.projectInfoText) {
        projectInfo = await extractProjectInfoFromText(cuaResult.projectInfoText, {
          url: rawUrl,
          contentType,
          llmConfig,
          source: 'cua',
        });
        analysisMode = 'cua+llm';
      } else if (finalParsed && finalParsed.content && finalParsed.content.length > 0) {
        projectInfo = await extractProjectInfoFromText(finalParsed.content, {
          url: rawUrl,
          contentType,
          llmConfig,
          source: 'cua_parsed',
        });
        analysisMode = 'cua+llm';
      } else {
        limitations.push('CUA did not provide enough information for ProjectInfo');
      }
    }
  }

  logger.debug('link_analyzer.decide_mode', {
    url: rawUrl,
    contentType,
    mode,
    analysisMode,
    reasons,
    signals: signalsWithDensity,
  });

  result.parsed = finalParsed;
  result.projectInfo = projectInfo;
  result.analysisMode = analysisMode;
  result.limitations = limitations;
  result.errors = errors;

  if (!result.parsed) {
    result.success = false;
    result.errors.push('Parsing failed');
  }

  logger.info(`Analysis finished for ${rawUrl} with mode ${result.analysisMode}`);
  return result;
}

module.exports = { analyzeUrl };
