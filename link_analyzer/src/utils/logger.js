// FILE: link_analyzer/src/utils/logger.js
function log(level, message, meta) {
  const timestamp = new Date().toISOString();
  const suffix = meta ? ` ${JSON.stringify(meta)}` : '';
  // eslint-disable-next-line no-console
  console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}${suffix}`);
}

module.exports = {
  info: (msg, meta) => log('info', msg, meta),
  warn: (msg, meta) => log('warn', msg, meta),
  error: (msg, meta) => log('error', msg, meta),
  debug: (msg, meta) => log('debug', msg, meta),
};
