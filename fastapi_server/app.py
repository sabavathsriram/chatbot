import os
import json
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
import logging
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATA_DIR = "kmit_data"
PERSIST_DIR = "db"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Clear existing database
if os.path.exists(PERSIST_DIR):
    shutil.rmtree(PERSIST_DIR)
    logger.info(f"Cleared existing database at '{PERSIST_DIR}'")

documents = []
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    qa_pairs = data
                elif isinstance(data, dict) and "qa_pairs" in data:
                    qa_pairs = data["qa_pairs"]
                else:
                    raise ValueError("JSON must be a list or have a 'qa_pairs' key")
                
                for i, pair in enumerate(qa_pairs):
                    if not isinstance(pair, dict) or "question" not in pair or "answer" not in pair:
                        logger.warning(f"Skipping invalid pair in {filename} at index {i}: {pair}")
                        continue
                    content = f"Q: {pair['question']}\nA: {pair['answer']}"
                    keywords = " ".join(pair['question'].lower().split())
                    # Add detail score to metadata
                    detail_score = len(pair['answer'].split('\n')) + sum(c.isdigit() for c in pair['answer'])  # Lines + digits
                    documents.append(Document(page_content=content, metadata={"source": filename, "qa_index": i, "keywords": keywords, "detail_score": detail_score}))
            logger.info(f"Loaded {filename} with {len(qa_pairs)} Q&A pairs")
        except Exception as e:
            logger.error(f"Error loading {filename}: {str(e)}")

if not documents:
    logger.error("No valid Q&A pairs loaded. Check your JSON files!")
    raise RuntimeError("No data to index")

embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb = Chroma.from_documents(documents=documents, embedding=embedding, persist_directory=PERSIST_DIR, collection_name="college_chatbot")

logger.info(f"Embeddings stored in '{PERSIST_DIR}'")
logger.info(f"Indexed Q&A pairs: {len(documents)}")

class QueryModel(BaseModel):
    query: str

GREETINGS = {"hi", "hello", "hey", "greetings"}
GENERAL_INTENTS = {"tell me about", "what about"}

@app.post("/query/")
async def fetch_answer(request: QueryModel):
    query_text = request.query.strip().lower()
    logger.info(f"Received query: {query_text}")

    if query_text in GREETINGS:
        return {"answer": "Hello! How can I assist you today? You can ask about admissions, courses, faculty, placements, and more!"}

    try:
        vectordb = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding, collection_name="college_chatbot")
        results = vectordb.similarity_search(query_text, k=5)
        if not results:
            logger.warning(f"No results found for query: {query_text}")
            return {"answer": "Sorry, I couldn’t find info on that. Try rephrasing or contact info@kmit.in for help!"}

        is_general = any(query_text.startswith(intent) for intent in GENERAL_INTENTS)
        query_keywords = set(query_text.split())

        best_match = None
        best_score = 0.0
        for result in results:
            question = result.page_content.split("\nA: ")[0].replace("Q: ", "").strip().lower()
            answer = result.page_content.split("\nA: ")[1].strip()
            question_keywords = set(result.metadata["keywords"].split())

            # Keyword overlap score
            overlap = len(query_keywords.intersection(question_keywords))
            keyword_score = overlap / max(len(query_keywords), 1)

            # Boost for exact substring match
            if query_text in question:
                keyword_score += 0.5

            # Detail score boost for general queries
            detail_boost = result.metadata["detail_score"] * 0.05 if is_general else 0

            # Total score: keyword + embedding rank + detail boost
            total_score = keyword_score + (1 - results.index(result) * 0.1) + detail_boost

            logger.info(f"Question: {question}, Keyword Score: {keyword_score}, Detail Boost: {detail_boost}, Total Score: {total_score}")

            if is_general and total_score >= 0.5:
                best_match = result
                break
            elif not is_general and total_score >= 0.7:
                best_match = result
                break
            elif total_score > best_score:
                best_score = total_score
                best_match = result

        if best_match and best_score >= (0.5 if is_general else 0.7):
            answer = best_match.page_content.split("A: ", 1)[1].strip()
            logger.info(f"Returning answer: {answer}")
            return {"answer": answer}
        else:
            answer = results[0].page_content.split("A: ", 1)[1].strip()
            logger.warning(f"No strong match for query: {query_text}, best score: {best_score}, falling back to: {answer}")
            return {"answer": answer}

    except Exception as e:
        logger.error(f"Error processing query '{query_text}': {str(e)}")
        return {"answer": "Sorry, something went wrong. Please try again!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)