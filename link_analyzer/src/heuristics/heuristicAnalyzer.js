// FILE: link_analyzer/src/heuristics/heuristicAnalyzer.js
function calculateTextDensity({ textLength, htmlLength }) {
  if (!htmlLength || htmlLength === 0) return 0;
  return textLength / htmlLength;
}

/**
 * @typedef {Object} HeuristicSignals
 * @property {number} htmlLength
 * @property {number} textLength
 * @property {number} canvasCount
 * @property {number} svgCount
 * @property {number} iframeCount
 * @property {number} imgCount
 * @property {number} linkCount
 * @property {number} inputCount
 */

/**
 * @typedef {Object} HeuristicDecision
 * @property {'cheap_only' | 'cheap_plus_llm' | 'need_cua'} mode
 * @property {string[]} reasons
 * @property {HeuristicSignals & { textDensity: number }} signals
 */

/**
 * Принимает ParsedPage + набор сигналов по DOM/HTML
 * и решает, нужно ли включать CUA.
 *
 * @param {import('../models/ParsedPage')} parsed
 * @param {HeuristicSignals} signals
 * @returns {HeuristicDecision}
 */
function decideAnalysisMode(parsed, signals) {
  const {
    htmlLength = 0,
    textLength = 0,
    canvasCount = 0,
    svgCount = 0,
    iframeCount = 0,
    imgCount = 0,
    linkCount = 0,
    inputCount = 0,
  } = signals || {};

  const textDensity = calculateTextDensity({ textLength, htmlLength });

  const reasons = [];
  let mode = 'cheap_only';

  const hasEnoughText = textLength >= 800; // порог «много текста»
  const hasSomeText = textLength >= 300; // порог «хватает для LLM»
  const isVeryLittleText = textLength < 300;

  const manyCanvasOrSvg = canvasCount + svgCount >= 2;
  const lowTextDensity = textDensity < 0.02; // очень мало текста на размер HTML
  const hugeHtml = htmlLength > 150000; // очень большая страница
  const manyInteractive = inputCount + iframeCount > 10;

  const likelyViewerLike =
    isVeryLittleText && (manyCanvasOrSvg || lowTextDensity || manyInteractive || hugeHtml);

  if (likelyViewerLike) {
    mode = 'need_cua';
    reasons.push('viewer_like_or_visual_editor');
  } else if (hasSomeText || hasEnoughText) {
    mode = 'cheap_plus_llm';
    reasons.push('enough_text_for_llm');
  } else if (isVeryLittleText) {
    mode = 'need_cua';
    reasons.push('too_little_text_for_llm');
  }

  return {
    mode,
    reasons,
    signals: {
      htmlLength,
      textLength,
      canvasCount,
      svgCount,
      iframeCount,
      imgCount,
      linkCount,
      inputCount,
      textDensity,
    },
  };
}

module.exports = {
  decideAnalysisMode,
  calculateTextDensity,
};
