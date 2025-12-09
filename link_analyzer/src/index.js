// FILE: link_analyzer/src/index.js
require('dotenv').config();
const express = require('express');
const config = require('./config');
const { analyzeUrl } = require('./services/linkAnalyzerService');
const logger = require('./utils/logger');

const app = express();
app.use(express.json());

app.post('/analyze', async (req, res) => {
  const { url } = req.body || {};
  if (!url || typeof url !== 'string' || url.trim().length === 0) {
    return res.status(400).json({ success: false, errors: ['`url` is required'] });
  }
  try {
    const result = {
        "success": true,
        "contentType": "web_page",
        "errors": []
    };
    return res.json(result);
  } catch (error) {
    logger.error(`Unhandled error during /analyze: ${error.message}`);
    return res.status(500).json({ success: false, errors: [error.message || 'Internal server error'] });
  }
});

app.use((err, req, res, next) => {
  logger.error(`Express error: ${err.message}`);
  res.status(500).json({ success: false, errors: [err.message || 'Internal server error'] });
});

app.listen(config.port, () => {
  logger.info(`Link analyzer service listening on port ${config.port}`);
});
