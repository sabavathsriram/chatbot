const express = require('express');
const { getChatbotResponse } = require('../controllers/chatController');
const router = express.Router();

router.post('/query', async (req, res) => {
  const { query } = req.body;
  if (!query) return res.status(400).json({ error: 'Query is required' });

  console.log('Received query:', query);
  try {
    const response = await getChatbotResponse(query, 'query');
    res.json(response);
  } catch (error) {
    console.error('Error in /query route:', error.message);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

router.post('/distance', async (req, res) => {
  const { location } = req.body;
  if (!location) return res.status(400).json({ error: 'Location is required' });

  console.log('Received distance query:', location);
  try {
    const response = await getChatbotResponse(location, 'distance');
    res.json(response);
  } catch (error) {
    console.error('Error in /distance route:', error.message);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

module.exports = router;