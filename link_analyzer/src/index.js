const createServer = require('./server');
const config = require('./config');
const logger = require('./utils/logger');

const app = createServer();

app.listen(config.port, () => {
  logger.info(`Link analyzer service listening on port ${config.port}`);
});
