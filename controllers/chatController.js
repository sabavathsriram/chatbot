const axios = require('axios');

async function getChatbotResponse(query) {
    try {
        // Fetch from FastAPI on port 8001
        console.log("Fetching from FastAPI:", query);
        const chromaResponse = await axios.post(
            'http://localhost:8001/query/', // Corrected port
            { query: query },
            { headers: { 'Content-Type': 'application/json' }, timeout: 10000 }
        );
        const retrievedContent = chromaResponse.data.answer;
        console.log("FastAPI response:", retrievedContent);

        // Optional: Uncomment if llama.cpp is running and needed
        /*
        console.log("Sending to llama.cpp:", query);
        const llmResponse = await axios.post(
            'http://localhost:8080/v1/completions',
            {
                prompt: `Context: ${retrievedContent}\nQuestion: ${query}\nAnswer:`,
                max_tokens: 150,
                temperature: 0.7,
                top_p: 0.9
            },
            { headers: { 'Content-Type': 'application/json' }, timeout: 60000 }
        );
        console.log("llama.cpp response:", llmResponse.data);
        return { answer: llmResponse.data.choices[0].text.trim() };
        */

        return { answer: retrievedContent }; // Use FastAPI response directly
    } catch (error) {
        console.error("Error:", error.message);
        if (error.code === 'ECONNREFUSED') {
            return { answer: "Error: A server isn’t running. Ensure FastAPI (8001) is active." };
        }
        return { answer: "Sorry, something went wrong. Please try again later." };
    }
}

module.exports = { getChatbotResponse };