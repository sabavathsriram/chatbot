const express = require('express');
const { getChatbotResponse } = require('../controllers/chatController');
const router = express.Router();

// router.post('/', async (req, res) => {
//     const { query } = req.body;
//     if (!query) return res.status(400).json({ error: "Query is required" });

//     try {
//         const response = await getChatbotResponse(query);
//         return res.json({ response });
//     } catch (error) {
//         console.error("Chatbot error:", error);
//         return res.status(500).json({ error: "Internal Server Error" });
//     }
// });
router.post("/query", async (req, res) => {
    const query = req.body.query;
    if (!query) return res.status(400).json({ error: "Query is required" });

    // Sample response (Replace with actual LLM response)
    res.json({ answer: `You asked: ${query}` });
});


module.exports = router;
