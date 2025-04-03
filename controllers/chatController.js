const { ChromaClient } = require("chromadb");
const { OpenAI } = require("@langchain/openai");  // ✅ NEW


const { RetrievalQAChain } = require("langchain/chains");
//const { OpenAI } = require("langchain/llms/openai");
require('dotenv').config();

const chroma = new ChromaClient({ path: "http://localhost:8000" });

async function getChatbotResponse(query) {
    try {
        // Step 1: Search ChromaDB
        const collection = await chroma.getCollection("college_chatbot");
        const searchResults = await collection.query({ query_texts: [query], n_results: 5 });

        let context = "";
        if (searchResults.documents.length > 0) {
            context = searchResults.documents.map(doc => doc.text).join("\n");
        }

        // Step 2: Generate Answer with LLM
        const llm = new OpenAI({
            modelName: "gpt-3.5-turbo",
            openAIApiKey: process.env.OPENAI_API_KEY,
        });

        const chain = RetrievalQAChain.fromLLM(llm, {
            retriever: { getRelevantDocuments: async () => [{ pageContent: context }] },
        });

        const response = await chain.call({ query });

        return response.text;
    } catch (error) {
        console.error("Chatbot Processing Error:", error);
        throw error;
    }
}

module.exports = { getChatbotResponse };
