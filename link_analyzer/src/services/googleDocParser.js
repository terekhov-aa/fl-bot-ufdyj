const axios = require('axios');
const { normalizeWhitespace } = require('../utils/textUtils');

async function fetchGoogleDoc(rawUrl) {
  const exportUrl = `${rawUrl}${rawUrl.includes('?') ? '&' : '?'}export?format=txt`;
  const altUrl = `${rawUrl}${rawUrl.includes('?') ? '&' : '?'}rm=demo&output=html&hl=en&forceanon=1&usp=chrome_ntp&pref=2&usp=embed_facebook&pli=1&rm=demo&output=html&rm=demo&output=html&usp=sharing`;
  try {
    const response = await axios.get(exportUrl, { timeout: 8000 });
    return normalizeWhitespace(response.data);
  } catch (error) {
    try {
      const altResponse = await axios.get(altUrl, { timeout: 8000 });
      return normalizeWhitespace(altResponse.data);
    } catch (altError) {
      throw altError;
    }
  }
}

module.exports = { fetchGoogleDoc };
