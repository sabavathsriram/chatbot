const axios = require('axios');

const getChatbotResponse = async (input, type) => {
  try {
    const endpoint = type === 'query' ? 'http://localhost:8001/query/' : 'http://localhost:8001/distance/';
    const payload = type === 'query' ? { query: input } : { location: input };

    const response = await axios.post(endpoint, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000,
      maxRedirects: 5 // Handle redirects explicitly
    });

    return response.data;
  } catch (error) {
    console.error(`Error forwarding to FastAPI (${type}):`, error.message);
    throw new Error(`Failed to get response from FastAPI: ${error.message}`);
  }
};

module.exports = { getChatbotResponse };