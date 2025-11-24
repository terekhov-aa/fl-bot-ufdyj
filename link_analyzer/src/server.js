const express = require('express');
const analyzeRoute = require('./routes/analyzeRoute');

function createServer() {
  const app = express();
  app.use(express.json({ limit: '2mb' }));
  app.use('/analyze', analyzeRoute);
  return app;
}

module.exports = createServer;
