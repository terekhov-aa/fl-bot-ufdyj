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

  const { parsed, signals, limitations, errors } = await cheapParseWithSignals(rawUrl, contentType);
  result.parsed = parsed;
  result.limitations = limitations;
  result.errors = errors;

  const { mode, reasons, signals: signalsWithDensity } = decideAnalysisMode(parsed, signals || {});
  let analysisMode = mode;
  let projectInfo = null;
  let parsedPage = parsed;

  if (mode === 'cheap_only') {
    analysisMode = 'cheap_parser';
  } else if (mode === 'cheap_plus_llm') {
    analysisMode = 'cheap_parser';
    if (parsedPage?.content) {
      analysisMode = 'cheap_parser+llm';
      projectInfo = await extractProjectInfoFromText(parsedPage.content, { url: rawUrl, contentType });
    }
  } else if (mode === 'need_cua') {
    analysisMode = 'cua';
    result.limitations.push('Heuristics: viewer-like page, CUA recommended');

    const cuaEnabled = config.enableCua;
    if (!cuaEnabled) {
      result.limitations.push('CUA mode requested but disabled via ENABLE_CUA=false');
      if (parsedPage?.content) {
        analysisMode = 'cheap_parser+llm_fallback';
        projectInfo = await extractProjectInfoFromText(parsedPage.content, { url: rawUrl, contentType });
      } else {
        analysisMode = 'cheap_parser';
      }
    } else {
      if (!config.cuaApiKey && !config.browserbaseApiKey && !config.cuaBaseUrl) {
        result.limitations.push('CUA credentials missing, using puppeteer fallback');
      }

      const cuaResult = await runCUAForProjectInfo(rawUrl, { contentType, signals: signalsWithDensity });
      if (cuaResult.limitations?.length) {
        result.limitations.push(...cuaResult.limitations);
      }
      if (cuaResult.errors?.length) {
        result.errors.push(...cuaResult.errors);
      }

      if (
        cuaResult?.parsedPageFromCUA &&
        (cuaResult.parsedPageFromCUA.content?.length || 0) > (parsedPage?.content?.length || 0)
      ) {
        parsedPage = cuaResult.parsedPageFromCUA;
      }

      if (cuaResult?.projectInfoFromCUA) {
        projectInfo = cuaResult.projectInfoFromCUA;
        analysisMode = 'cua_direct_project_info';
      } else if (cuaResult?.projectInfoText) {
        projectInfo = await extractProjectInfoFromText(cuaResult.projectInfoText, {
          url: rawUrl,
          contentType,
          source: 'cua',
        });
        analysisMode = 'cua+llm';
      } else if (parsedPage?.content) {
        projectInfo = await extractProjectInfoFromText(parsedPage.content, {
          url: rawUrl,
          contentType,
          source: 'cua_parsed',
        });
        analysisMode = 'cua+llm';
      } else {
        result.limitations.push('CUA did not return enough content for ProjectInfo');
      }
    }
  }

  if (!parsedPage) {
    result.success = false;
    result.errors.push('Parsing failed');
  }

  result.analysisMode = analysisMode;
  result.parsed = parsedPage;
  result.projectInfo = projectInfo;

  logger.info(
    `link_analyzer.decide_mode url=${rawUrl} mode=${mode} analysisMode=${analysisMode} reasons=${reasons.join(',')} ` +
      `signals=${JSON.stringify(signalsWithDensity)}`,
  );

  return result;
}

module.exports = { analyzeUrl };
