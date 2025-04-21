import os
import json
import requests
import shutil
import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
import logging
import time
from typing import List, Dict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="KMIT Chatbot", description="Chatbot for KMIT queries using RAG with Gemini AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

DATA_DIR = "kmit_data"
PERSIST_DIR = os.path.join(os.getcwd(), "db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)

# Check disk space
def check_disk_space(path):
    disk = psutil.disk_usage(path)
    free_mb = disk.free / (1024 * 1024)
    logger.info(f"Disk space at {path}: {free_mb:.2f} MB free")
    return free_mb

check_disk_space(os.path.dirname(PERSIST_DIR))

# Process JSON with larger chunks
def process_json(data: Dict, chunk_size=500) -> List[Dict]:
    def flatten(d, prefix=""):
        content = []
        for key, value in d.items():
            new_key = f"{prefix}_{key}" if prefix else key
            if isinstance(value, dict):
                content.extend(flatten(value, new_key))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    content.extend(flatten({f"{new_key}_{i}": v}, new_key))
            else:
                content.append(f"{new_key}: {str(value)}")
        return content
    
    def chunk_text(text):
        words = text.split()
        return [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    
    items = []
    if isinstance(data, dict):
        flat_content = flatten(data)
        for text in flat_content:
            chunks = chunk_text(text)
            for chunk in chunks:
                items.append({"fields": [chunk], "raw": {prefix: value for prefix, value in [line.split(": ", 1) for line in [text]]}})
    elif isinstance(data, list):
        for i, item in enumerate(data):
            flat_content = flatten({f"item_{i}": item})
            for text in flat_content:
                chunks = chunk_text(text)
                for chunk in chunks:
                    items.append({"fields": [chunk], "raw": {f"item_{i}": item}})
    return items

# Load and process documents from JSON files
documents = []
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                category = "General"
                fn_lower = filename.lower()
                if "admissions" in fn_lower or "eapcet" in fn_lower or "ecet" in fn_lower:
                    category = "Admissions"
                elif "placements" in fn_lower:
                    category = "Placements"
                elif "faculty" in fn_lower or "hods" in fn_lower:
                    category = "Faculty"
                elif "infrastructure" in fn_lower or "facilities" in fn_lower or "sports" in fn_lower or "library" in fn_lower:
                    category = "Campus Facilities"
                elif "regulations" in fn_lower or "autonomous" in fn_lower:
                    category = "Exams & Regulations"
                elif "courses" in fn_lower or "syllabi" in fn_lower:
                    category = "Courses"
                elif "administration" in fn_lower or "generalinfo" in fn_lower:
                    category = "Administration"

                groups = process_json(data)
                for group in groups:
                    content = "\n".join(group["fields"])
                    if not content.strip():
                        logger.warning(f"Empty content in {filename}")
                        continue
                    keywords = " ".join(set(word for line in group["fields"] for word in line.lower().split()))
                    keywords += f" {category.lower()} kmit {category.replace(' & ', ' ').replace('Exams', 'exam').replace('Regulations', 'regulation')}"
                    metadata = {
                        "source": filename,
                        "category": category,
                        "keywords": keywords,
                        "raw_data": json.dumps(group["raw"])
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
                logger.info(f"Loaded {filename}: {len(groups)} chunks, category {category}, sample content: {content[:100]}...")
        except Exception as e:
            logger.error(f"Error in {filename}: {e}")

if not documents:
    logger.error("No documents loaded!")
    raise RuntimeError("No JSON files in kmit_data/")

# Initialize ChromaDB
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
try:
    vectordb = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding, collection_name="kmit")
    doc_count = vectordb._collection.count()
    logger.info(f"Existing ChromaDB: {doc_count} documents")
    if doc_count == 0:
        logger.info("Empty ChromaDB, rebuilding...")
        if os.path.exists(PERSIST_DIR):
            shutil.rmtree(PERSIST_DIR)
            logger.info("Cleared existing ChromaDB")
        vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR, collection_name="kmit")
except Exception as e:
    logger.error(f"ChromaDB load failed ({e}), creating new...")
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        logger.info("Cleared existing ChromaDB")
    vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR, collection_name="kmit")

logger.info(f"ChromaDB: {vectordb._collection.count()} documents")
if vectordb._collection.count() == 0:
    logger.error("Failed to index documents!")
    raise RuntimeError("ChromaDB indexing failed")

# Gemini API with retry logic
GEMINI_API_KEY = "AIzaSyCqhE0zaP4Ot3RviLKomupYDnmrYMXrs30"  # Replace with valid key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def call_gemini_api(prompt: str, max_retries=3) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.005}
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return f"API error after {max_retries} attempts: {str(e)}. Please try again later."
        except (KeyError, IndexError) as e:
            logger.error(f"Gemini API parsing error: {e}")
            return "Error processing the query due to API response issue."
    return "Unexpected error in API call."

# Query model
class QueryModel(BaseModel):
    query: str

GREETINGS = {"hi", "hello", "hey", "greetings"}

# Search documents with broad retrieval
def hybrid_search(query: str, category: str, source_hint: str = None, k: int = 80) -> List[Document]:
    expanded_query = f"{query.lower()} kmit what where when about details info"
    category_keywords = {
        "admissions": "eligibility eapcet ecet lateral entry tuition fees contact fee structure seats",
        "courses": "offered btech cse csm data science it programs intake",
        "faculty": "members csm hod phd mtech professors staff",
        "exams & regulations": "schedule syllabus regulations autonomous exam dates",
        "placements": "salary package students placed companies offers intuit ctc job",
        "campus facilities": "library sports gym auditorium badminton football chess table tennis caroms volleyball basketball hostel bus timings",
        "administration": "principal location departments founder ranking timing blocks college timings campus size about where"
    }
    if category in category_keywords:
        expanded_query += f" {category_keywords[category]}"
    
    try:
        results = vectordb.similarity_search(expanded_query, k=k)
        logger.info(f"Search '{query}' (expanded: '{expanded_query[:100]}...'): {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# Extract answer with comprehensive context
def extract_answer(query: str, results: List[Document]) -> str:
    if not results:
        return "I don’t have enough information to answer this. Please contact info@kmit.in."
    
    # Use all retrieved context
    full_context = "\n".join(doc.page_content for doc in results)
    if not full_context.strip():
        return "I don’t have enough information to answer this. Please contact info@kmit.in."
    
    context_lines = full_context.count('\n') + 1
    logger.info(f"Full context sample: {full_context[:200]}...")
    prompt = f"""
    You are a KMIT chatbot using RAG with Gemini AI. Answer the query: '{query}' by compiling and presenting ALL relevant information from the provided context, which is derived from JSON files in kmit_data. Include every detail related to the query, even if incomplete or scattered across the context. For general queries (e.g., 'what is kmit', 'where is kmit'), summarize all applicable data about KMIT. Avoid inventing or generalizing beyond the context, and use the fallback message ('I don’t have enough information to answer this. Please contact info@kmit.in.') only if no relevant data is present. Match the query to these categories and include all data:
    - Admissions: Eligibility, entrance tests, seat allocation, lateral entry, fees, contact.
    - Courses: All courses offered and intake details.
    - Faculty: All faculty names, titles, and qualifications.
    - Exams & Regulations: All exam schedules or regulations.
    - Placements: All placement stats (companies, offers, salaries) for all batches.
    - Campus Facilities: All data for library, sports, gym, auditorium, timings.
    - Administration: All data for principal, location, departments, founder, ranking, timing, blocks.
    Context:
    {full_context}
    Answer:
    """
    logger.info(f"Processing query: {query} with context from {len(results)} documents (total {context_lines} lines)")
    return call_gemini_api(prompt)

@app.post("/query/")
async def fetch_answer(request: QueryModel):
    query_text = request.query.strip().lower()
    logger.info(f"Received query: {query_text}")

    if query_text in GREETINGS:
        return {"answer": "Hello! I’m your KMIT chatbot. Ask me about admissions, courses, faculty, exams, placements, campus facilities, or administration!"}

    try:
        # Broad category detection
        category = "General"
        source_hint = None
        categories = {
            "admissions": ("Admissions", "admissions.json"),
            "courses": ("Courses", "vas.json"),
            "faculty": ("Faculty", "csm_faculty.json"),
            "exams": ("Exams & Regulations", "regu.json"),
            "placements": ("Placements", "placements.json"),
            "facilities": ("Campus Facilities", "infrastructure.json"),
            "administration": ("Administration", "generalinfo.json")
        }
        for key in categories.keys():
            if key in query_text or (key == "facilities" and any(word in query_text for word in ["library", "sports", "gym", "auditorium", "timings"])) or \
               (key == "placements" and any(word in query_text for word in ["salary", "placement", "job", "company"])) or \
               (key == "admissions" and any(word in query_text for word in ["fee", "eligibility", "contact", "seat"])) or \
               (key == "administration" and any(word in query_text for word in ["principal", "founder", "timing", "blocks", "ranking", "where", "what"])):
                category = categories[key][0]
                source_hint = categories[key][1]
                break

        results = hybrid_search(query_text, category, source_hint)
        if not results:
            logger.info(f"No results for: {query_text}")
            return {"answer": "I don’t have enough information to answer this. Please contact info@kmit.in."}

        answer = extract_answer(request.query, results)
        logger.info(f"Answer: {answer}")
        return {"answer": answer}

    except Exception as e:
        logger.error(f"Query error: {e}")
        return {"answer": f"Something went wrong: {str(e)}. Please try again or contact info@kmit.in."}

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise