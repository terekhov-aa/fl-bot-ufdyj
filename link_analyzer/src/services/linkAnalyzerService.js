// FILE: link_analyzer/src/services/linkAnalyzerService.js
const LinkAnalysisResult = require('../models/LinkAnalysisResult');
const { detectContentType } = require('./contentTypeDetector');
const { cheapParseWithSignals } = require('./cheapParser');
const { decideAnalysisMode } = require('../heuristics/heuristicAnalyzer');
const { extractProjectInfoFromText } = require('./llmClient');
const { runCUAForProjectInfo } = require('./cuaService');
const logger = require('../utils/logger');
const config = require('../config');

async function analyzeUrl(url) {
  const result = new LinkAnalysisResult();
  result.parsed = null;
  result.projectInfo = null;
  result.limitations = [];
  result.errors = [];

  try {
    const contentType = detectContentType(url);
    result.contentType = contentType;

    const { parsed, limitations, errors, signals } = await cheapParseWithSignals(url, contentType);
    if (limitations) result.limitations.push(...limitations);
    if (errors) result.errors.push(...errors);
    result.parsed = parsed;

    const decision = decideAnalysisMode(parsed, signals);
    logger.info('Analysis mode decision', { mode: decision.mode, reasons: decision.reasons, signals: decision.signals });

    if (decision.mode === 'cheap_only') {
      result.analysisMode = 'cheap_parser';
      result.limitations.push(...decision.reasons);
      return result;
    }

    if (decision.mode === 'cheap_plus_llm') {
      result.analysisMode = 'cheap_parser+llm';
      if (parsed && parsed.content) {
        const projectInfo = await extractProjectInfoFromText(parsed.content, {
          url,
          contentType,
          source: 'cheap_parser',
        });
        if (projectInfo) {
          result.projectInfo = projectInfo;
        } else {
          result.limitations.push('LLM extraction unavailable');
        }
      } else {
        result.limitations.push('No parsed content for LLM extraction');
      }
      result.limitations.push(...decision.reasons);
      return result;
    }

    if (decision.mode === 'need_cua') {
      result.analysisMode = config.cuaGloballyEnabled ? 'cua' : 'cheap_parser';
      logger.info('Invoking Stagehand CUA workflow', { model: config.cuaModel, signals });
      const cuaOutcome = await runCUAForProjectInfo(url, { contentType, signals });
      result.limitations.push(...cuaOutcome.limitations);
      result.errors.push(...cuaOutcome.errors);

      if (cuaOutcome.parsedPageFromCUA) {
        result.parsed = cuaOutcome.parsedPageFromCUA;
      }
      if (cuaOutcome.projectInfoFromCUA) {
        result.projectInfo = cuaOutcome.projectInfoFromCUA;
      }

      if (!result.projectInfo) {
        const contentForLLM =
          (cuaOutcome.projectInfoText && cuaOutcome.projectInfoText.trim()) ||
          (cuaOutcome.parsedPageFromCUA && cuaOutcome.parsedPageFromCUA.content) ||
          (parsed && parsed.content) ||
          '';
        if (contentForLLM) {
          const projectInfo = await extractProjectInfoFromText(contentForLLM, {
            url,
            contentType,
            source: cuaOutcome.parsedPageFromCUA ? 'cua' : 'cheap_parser',
          });
          if (projectInfo) {
            result.projectInfo = projectInfo;
          } else {
            result.limitations.push('LLM extraction unavailable');
          }
        } else {
          result.limitations.push('No content available for project extraction');
        }
      }
      result.limitations.push(...decision.reasons);
      return result;
    }

    result.limitations.push('Unknown analysis mode');
    return result;
  } catch (error) {
    logger.error(`Unexpected analysis error: ${error.message}`);
    result.success = false;
    result.errors.push(error.message || 'Unknown error');
    return result;
  }
}

module.exports = {
  analyzeUrl,
};
