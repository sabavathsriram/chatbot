const express = require('express');
const { getChatbotResponse } = require('../controllers/chatController');
const router = express.Router();

router.post("/query", async (req, res) => {
    const { query } = req.body;
    if (!query) return res.status(400).json({ error: "Query is required" });

    console.log("Received query:", query);
    try {
        const response = await getChatbotResponse(query);
        res.json(response);
    } catch (error) {
        console.error("Error in route:", error.message);
        res.status(500).json({ error: "Something went wrong. Check server logs." });
    }
});

module.exports = router;