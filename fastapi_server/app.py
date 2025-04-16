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
from typing import List, Dict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="KMIT Chatbot", description="Chatbot for KMIT queries")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

# Process JSON
def process_json(data: Dict) -> List[Dict]:
    items = []
    def flatten(d, prefix=""):
        content = []
        for key, value in d.items():
            new_key = f"{prefix}_{key}" if prefix else key
            if isinstance(value, dict):
                content.extend(flatten(value, new_key))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    content.extend(flatten({f"{new_key}_{i}": v}))
            else:
                content.append(f"{new_key}: {str(value)}")
        return content
    if isinstance(data, dict):
        items.append({"fields": flatten(data), "raw": data})
    elif isinstance(data, list):
        for i, item in enumerate(data):
            items.append({"fields": flatten({f"item_{i}": item}), "raw": item})
    return items

# Load documents
documents = []
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                category = "General"
                fn_lower = filename.lower()
                if "admission" in fn_lower or "eapcet" in fn_lower or "ecet" in fn_lower:
                    category = "Admissions"
                elif "placement" in fn_lower:
                    category = "Placements"
                elif "faculty" in fn_lower or "hods" in fn_lower:
                    category = "Faculty"
                elif "facilit" in fn_lower or "sport" in fn_lower or "library" in fn_lower or "infrastructure" in fn_lower or "labs" in fn_lower:
                    category = "Campus Facilities"
                elif "regulation" in fn_lower or "autonomous" in fn_lower:
                    category = "Regulations"
                elif "event" in fn_lower or "notification" in fn_lower:
                    logger.info(f"Skipping Notifications file: {filename}")
                    continue
                
                groups = process_json(data)
                for group in groups:
                    content = "\n".join(group["fields"])
                    if not content.strip():
                        logger.warning(f"Empty content in {filename}")
                        continue
                    keywords = " ".join(set(word for line in group["fields"] for word in line.lower().split()))
                    keywords += f" {category.lower()} kmit admissions fees eapcet ecet lateral entry tuition special nba contact placements highest salary average salary students placed companies visited offers campus facilities sports library gym badminton basketball football volleyball yoga auditorium labs granthalaya training tournaments regulations autonomous jntuh courses"
                    metadata = {
                        "source": filename,
                        "category": category,
                        "keywords": keywords,
                        "raw_data": json.dumps(group["raw"])
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
                logger.info(f"Loaded {filename}: {len(groups)} documents, category {category}")
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
            try:
                shutil.rmtree(PERSIST_DIR)
                logger.info("Cleared existing ChromaDB")
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot clear db/: {e}. Creating new...")
        os.makedirs(PERSIST_DIR, exist_ok=True)
        vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR, collection_name="kmit")
except Exception as e:
    logger.info(f"ChromaDB load failed ({e}), creating new...")
    if os.path.exists(PERSIST_DIR):
        try:
            shutil.rmtree(PERSIST_DIR)
            logger.info("Cleared existing ChromaDB")
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot clear db/: {e}")
    os.makedirs(PERSIST_DIR, exist_ok=True)
    vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR, collection_name="kmit")

logger.info(f"ChromaDB: {vectordb._collection.count()} documents")
if vectordb._collection.count() == 0:
    logger.error("Failed to index documents!")
    raise RuntimeError("ChromaDB indexing failed")

# Gemini API
GEMINI_API_KEY = "AIzaSyDqpJweZrDuBdeC8REuVk9p3kqUMCB1PCs"  # Replace with valid key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def call_gemini_api(prompt: str) -> str:
    if not GEMINI_API_KEY:
        logger.error("No Gemini API key provided")
        return "Gemini API key missing, cannot process query."
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 500, "temperature": 0.005}
    }
    try:
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Gemini HTTP error: {e}")
        return "Gemini API error, please try again."
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None

# Query model
class QueryModel(BaseModel):
    query: str

GREETINGS = {"hi", "hello", "hey", "greetings"}

# Search documents
def hybrid_search(query: str, category: str, source_hint: str = None, k: int = 60) -> List[Document]:
    try:
        # Query expansion
        expanded_query = query.lower()
        if any(x in expanded_query for x in ["admission", "fees", "eapcet", "ecet", "strucrure", "tuition", "eligibility", "contact"]):
            expanded_query += " admissions eligibility eapcet ecet lateral entry tuition special nba contact fees structure"
        elif any(x in expanded_query for x in ["placement", "salary", "package", "placed", "offers", "ctc", "highest", "average", "companies", "students"]):
            expanded_query += " placements highest salary average salary students placed students registered companies visited offers ctc year"
        elif any(x in expanded_query for x in ["campus", "facilit", "library", "sport", "gym", "labs", "badminton", "football", "basketball", "yoga", "auditorium"]):
            expanded_query += " campus facilities sports library gym badminton basketball football volleyball yoga auditorium labs granthalaya training tournaments"
        elif any(x in expanded_query for x in ["regulation", "autonomous", "semester"]):
            expanded_query += " regulations autonomous semester cie see kr24 kr23 kr21 kr20"
        results = vectordb.similarity_search(expanded_query, k=k)
        # Prioritize by category and source
        seen_content = set()
        prioritized = []
        for doc in results:
            if (doc.metadata["category"] == category or (source_hint and source_hint in doc.metadata["source"])) and doc.page_content not in seen_content:
                prioritized.append(doc)
                seen_content.add(doc.page_content)
        for doc in results:
            if doc.page_content not in seen_content:
                prioritized.append(doc)
                seen_content.add(doc.page_content)
        logger.info(f"Search '{query}' (expanded: '{expanded_query}', category: {category}, source_hint: {source_hint}): {len(prioritized)} results from {', '.join(set(doc.metadata['source'] for doc in prioritized))}")
        return prioritized[:30]
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# Extract answer
def extract_answer(query: str, results: List[Document]) -> str:
    context = "\n".join(list(dict.fromkeys(doc.page_content for doc in results)))
    if not context.strip():
        return "I don’t have enough information to answer this. Please contact info@kmit.in."
    prompt = f"""
    You are a KMIT chatbot competing to deliver 100% accurate answers from JSON files for Admissions, Placements, and Campus Facilities queries. Answer using only the provided context, matching data exactly. Do not invent, generalize, or add external details. If the context lacks a clear answer, say: "I don’t have enough information to answer this. Please contact info@kmit.in."
    Context:
    {context[:6000]}
    Query: {query}
    Instructions:
    - Answer concisely, using exact context data from JSON files.
    - For admissions queries (e.g., 'admissions,' 'fees,' 'eligibility,' 'eapcet,' 'contact'), include eligibility (10+2 with Mathematics, Physics, Chemistry, EAPCET), seat allocation (70% EAPCET, 30% Management/NRI), lateral entry (20% via ECET, second year), fee structure (all years, exact figures: Year I: Tuition ₹103,000, Special ₹5,500, NBA ₹3,000; Years II-IV: Tuition ₹103,000, Special ₹2,500, NBA ₹3,000), contact (6302140205).
    - For placement queries (e.g., 'placements,' 'salary,' 'package,' 'placed,' 'offers'), include full stats if general (2023-2024, 103 companies, 662 offers, 557 registered, 511 placed, 9.69 LPA average, 49.8 LPA highest by Intuit) or specific metrics:
      - 'highest salary,' 'highest package,' 'highest placement,' 'highest ctc': Return '49.8 LPA by Intuit, 2023-2024.'
      - 'who got highest salary': Return student name if available (e.g., SreeLaya); else, 'No student name provided.'
      - 'average salary,' 'average package': Return '9.69 LPA, 2023-2024.'
      - 'students placed,' 'total number of students placed,' 'secured placements': Return '511 students were placed in the 2023-2024 batch.'
      - 'companies visited': Return '103 companies visited in the 2023-2024 batch.'
      - 'offers': Return '662 offers were rolled out in the 2023-2024 batch.'
    - For campus facilities queries (e.g., 'campus,' 'facilities,' 'sports,' 'library,' 'gym'), include indoor sports (badminton: professional-standard court behind Block B, annual competitions; yoga: daily coaching 4-5:30 pm; chess, table tennis, caroms: dedicated rooms above auditorium, intra-college tournaments), outdoor sports (football: large field, daily coaching, 12-member team, three intra-college events; basketball: professional-standard court, tournaments at BITS Hyderabad 24-27 Jan 2019, Vidya Jyothi 2-3 Apr 2019, KMIT hosted 17-18 Jan 2015; volleyball: field next to basketball court, daily coaching, intra-college events), library (KMIT Granthalaya, hours/resources if available), gym (faculty use 3:30-4:45 pm), auditorium, training (basketball, taekwondo, volleyball, kabaddi, inter-branch tournaments, proposed inter-collegiate basketball tournaments, fitness training twice weekly, inter-class competitions 2-3 times yearly).
    - For specific facility queries:
      - 'sports,' 'sports facility': List all indoor and outdoor sports, training, tournaments.
      - 'library': Return 'KMIT Granthalaya' with hours/resources if available, else clarify.
      - 'labs,' 'laboratories': Provide lab details if available, else clarify.
      - 'gym,' 'auditorium': Return specific details (e.g., gym hours, auditorium availability).
    - Handle typos (e.g., 'strucrure' for 'structure,' 'placemsnts' for 'placements') by mapping to correct terms.
    - For numerical queries (e.g., 'how many students placed,' 'fee amount'), extract exact numbers (e.g., 511, ₹103,000).
    - Use full department names (e.g., Computer Science & Engineering).
    - Ensure salary figures are precise (e.g., 49.8 LPA, 9.69 LPA with year).
    - Exclude unrelated data (e.g., no company name for 'who got highest salary').
    - Clarify incomplete data (e.g., no library hours, no student name).
    Answer:
    """
    logger.info(f"Processing query: {query} with context from {', '.join(set(doc.metadata['source'] for doc in results))}")
    response = call_gemini_api(prompt)
    return response if response else "I don’t have enough information to answer this. Please contact info@kmit.in."

# Preprocess query
def preprocess_query(query: str) -> str:
    query = query.strip().lower()
    synonyms = [
        ("admissions", "admission details"),
        ("admission", "admission details"),
        ("fee strucrure", "admission fees"),
        ("fee structure", "admission fees"),
        ("fees", "admission fees"),
        ("tuition", "admission fees"),
        ("eligibility", "admission eligibility"),
        ("eapcet", "admission eligibility"),
        ("ecet", "admission eligibility"),
        ("lateral entry", "admission eligibility"),
        ("contact", "admission contact"),
        ("placements", "placement statistics"),
        ("placemsnts", "placement statistics"),
        ("highest salary", "placement highest salary"),
        ("highest package", "placement highest salary"),
        ("highest placement", "placement highest salary"),
        ("highest ctc", "placement highest salary"),
        ("who got highest salary", "placement highest salary student"),
        ("which student got highest salary", "placement highest salary student"),
        ("average salary", "placement average salary"),
        ("average package", "placement average salary"),
        ("students placed", "placement students placed"),
        ("total number of students placed", "placement students placed"),
        ("secured placements", "placement students placed"),
        ("got placements", "placement students placed"),
        ("how many students placed", "placement students placed"),
        ("companies visited", "placement companies visited"),
        ("offers", "placement offers"),
        ("campus facilities", "campus infrastructure"),
        ("facilities", "campus infrastructure"),
        ("campus", "campus infrastructure"),
        ("sports", "campus sports"),
        ("sports facility", "campus sports"),
        ("does kmit provide any sports facility", "campus sports"),
        ("library", "campus library"),
        ("labs", "campus labs"),
        ("laboratories", "campus labs"),
        ("does kmit provide any labs facility", "campus labs"),
        ("gym", "campus gym"),
        ("auditorium", "campus auditorium"),
        ("tournaments", "campus sports"),
        ("badminton", "campus sports"),
        ("football", "campus sports"),
        ("basketball", "campus sports"),
        ("volleyball", "campus sports"),
        ("yoga", "campus sports"),
        ("regulations of kmit", "academic regulations"),
        ("is kmit autonomous", "autonomous status"),
        ("courses offered in kmit", "courses offered"),
    ]
    for key, value in synonyms:
        if key in query:
            query = query.replace(key, value)
            break
    return query

@app.post("/query/")
async def fetch_answer(request: QueryModel):
    query_text = preprocess_query(request.query)
    logger.info(f"Processed query: {query_text}")

    if query_text in GREETINGS:
        return {"answer": "Hello! I’m your KMIT assistant. Ask me about admissions, placements, campus facilities, or more!"}

    try:
        # Category and source hint
        category = "General"
        source_hint = None
        categories = {
            "admission details": ("Admissions", "admissions.json"),
            "admission fees": ("Admissions", "admissions.json"),
            "admission eligibility": ("Admissions", "admissions.json"),
            "admission contact": ("Admissions", "admissions.json"),
            "placement statistics": ("Placements", "placements.json"),
            "placement highest salary": ("Placements", "placements.json"),
            "placement highest salary student": ("Placements", "placements.json"),
            "placement average salary": ("Placements", "placements.json"),
            "placement students placed": ("Placements", "placements.json"),
            "placement companies visited": ("Placements", "placements.json"),
            "placement offers": ("Placements", "placements.json"),
            "campus infrastructure": ("Campus Facilities", "infrastructure.json"),
            "campus sports": ("Campus Facilities", "infrastructure.json"),
            "campus library": ("Campus Facilities", "infrastructure.json"),
            "campus labs": ("Campus Facilities", "infrastructure.json"),
            "campus gym": ("Campus Facilities", "infrastructure.json"),
            "campus auditorium": ("Campus Facilities", "infrastructure.json"),
            "academic regulations": ("Regulations", "regu.json"),
            "autonomous status": ("Regulations", "regu.json"),
            "courses offered": ("General", None),
        }
        for key, (cat, src) in categories.items():
            if key in query_text:
                category = cat
                source_hint = src
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
        return {"answer": "Something went wrong. Please contact info@kmit.in."}

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise