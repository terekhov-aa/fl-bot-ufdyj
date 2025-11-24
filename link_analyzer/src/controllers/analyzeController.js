const linkAnalyzerService = require('../services/linkAnalyzerService');
const logger = require('../utils/logger');

async function analyzeLink(req, res) {
  const { url } = req.body || {};
  if (!url || typeof url !== 'string') {
    return res.status(400).json({ success: false, error: 'Field "url" is required' });
  }

  try {
    const result = await linkAnalyzerService.analyzeUrl(url);
    return res.json(result);
  } catch (error) {
    logger.error(`Failed to analyze link: ${error.message}`);
    return res.status(500).json({ success: false, error: 'Internal server error' });
  }
}

module.exports = { analyzeLink };
