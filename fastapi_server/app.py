import os
import json
import requests
import shutil
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
import logging
import time
from typing import List, Dict
import math
from fuzzywuzzy import process

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="KMIT Chatbot", description="Chatbot for KMIT queries using RAG with Gemini AI and distance calculation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5500", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA_DIR = "kmit_data"
PERSIST_DIR = os.path.join(os.getcwd(), "db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)

# KMIT coordinates (Narayanguda, Hyderabad)
KMIT_COORDS = (17.4045, 78.4948)

# Local lookup table for common Hyderabad locations
HYDERABAD_LOCATIONS = {
    "LB Nagar": (17.3498, 78.5513),
    "LBNagar": (17.3498, 78.5513),
    "Dilsukhnagar": (17.3688, 78.5247),
    "Dilsukh Nagar": (17.3688, 78.5247),
    "Uppal": (17.4056, 78.5591),
    "Kukatpally": (17.4931, 78.3996),
    "HiTech City": (17.4416, 78.3804),
    "Banjara Hills": (17.4108, 78.4294),
    "Jubilee Hills": (17.4328, 78.4071),
    "Ameerpet": (17.4375, 78.4483)
}

# Check disk space
def check_disk_space(path):
    disk = psutil.disk_usage(path)
    free_mb = disk.free / (1024 * 1024)
    logger.info(f"Disk space at {path}: {free_mb:.2f} MB free")
    return free_mb

check_disk_space(os.path.dirname(PERSIST_DIR))

# Calculate distance
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

# Normalize location
def normalize_location(address: str) -> str:
    address = address.strip().lower()
    normalizations = {
        "lbnagar": "LB Nagar",
        "lb nagar": "LB Nagar",
        "dilsukhnagar": "Dilsukhnagar",
        "dilsukh nagar": "Dilsukhnagar",
        "kukatpalli": "Kukatpally",
        "kukat pally": "Kukatpally",
        "hitech city": "HiTech City",
        "hi-tech city": "HiTech City",
        "banjara hills": "Banjara Hills",
        "jubilee hills": "Jubilee Hills",
        "ameerpet": "Ameerpet"
    }
    for key, value in normalizations.items():
        if key in address:
            address = address.replace(key, value)
    return address.title()

# Geocode address
def geocode_address(address: str) -> tuple:
    normalized_address = normalize_location(address)
    if normalized_address in HYDERABAD_LOCATIONS:
        logger.info(f"Found {normalized_address} in local lookup table")
        return HYDERABAD_LOCATIONS[normalized_address]

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "KMITChatbot/1.0 (contact: info@kmit.in)"}
    params = {"format": "json", "limit": 10, "addressdetails": 1}
    fallbacks = ["", ", Hyderabad", ", Telangana", ", India"]
    try:
        for suffix in fallbacks:
            query = f"{normalized_address}{suffix}"
            params["q"] = query
            logger.info(f"Geocoding attempt: {query}")
            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            results = response.json()
            if results:
                for result in results:
                    address_details = result.get("address", {})
                    if (
                        address_details.get("city") == "Hyderabad" or
                        address_details.get("state") == "Telangana" or
                        address_details.get("county") == "Hyderabad"
                    ):
                        return float(result["lat"]), float(result["lon"])
                return float(results[0]["lat"]), float(results[0]["lon"])
            time.sleep(1)
        logger.warning(f"No geocoding results for address: {address}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding error for {address}: {e}")
        return None

# Process JSON with simplified handling
def process_json(data: Dict, filename: str, chunk_size=1000) -> List[Dict]:
    def flatten(d, prefix=""):
        content = []
        for key, value in d.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                content.extend(flatten(value, new_key))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    content.extend(flatten({f"{new_key}[{i}]": v}, new_key))
            else:
                content.append(f"{new_key}: {str(value)}")
        return content

    items = []
    raw_data = json.dumps(data, indent=2)
    logger.info(f"Processing {filename}: {raw_data[:500]}...")
    flat_content = flatten(data)
    full_text = "\n".join(flat_content)
    if not full_text.strip():
        logger.warning(f"No content extracted from {filename}")
        return []

    # Chunk large content
    words = full_text.split()
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    for chunk in chunks:
        items.append({"fields": [chunk], "raw": data})
    logger.info(f"Extracted {len(items)} chunks from {filename}")
    return items

# Load and process documents
documents = []
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                fn_lower = filename.lower()
                category = "General"
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
                elif "courses" in fn_lower or "syllabi" in fn_lower or "vas" in fn_lower:
                    category = "Courses"
                elif "generalinfo" in fn_lower or "administration" in fn_lower:
                    category = "Administration"

                groups = process_json(data, filename)
                if not groups:
                    logger.warning(f"No content extracted from {filename}")
                    continue
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
                        "raw_data": json.dumps(group["raw"]),
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
                    logger.info(f"Created document from {filename}: category={category}, content={content[:100]}...")
                logger.info(f"Loaded {filename}: {len(groups)} chunks, category={category}")
        except Exception as e:
            logger.error(f"Error in {filename}: {e}")

if not documents:
    logger.error("No documents loaded!")
    raise RuntimeError("No JSON files in kmit_data/")

# Initialize ChromaDB
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
vectordb = None
try:
    # Clear existing ChromaDB
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        logger.info(f"Cleared existing ChromaDB at {PERSIST_DIR}")
    os.makedirs(PERSIST_DIR, exist_ok=True)
    unique_collection = f"kmit_{int(time.time())}"
    vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR, collection_name=unique_collection)
    logger.info(f"Created new collection '{unique_collection}' with {len(documents)} documents")
except Exception as e:
    logger.error(f"ChromaDB creation failed: {e}")
    raise RuntimeError("Failed to initialize ChromaDB")

logger.info(f"ChromaDB: {vectordb._collection.count()} documents")
if vectordb._collection.count() == 0:
    logger.error("Failed to index documents!")
    raise RuntimeError("ChromaDB indexing failed")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDAlNnYVMb645dUf-UQNS4bqx8qEd7yOks")  # Replace with valid key
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def call_gemini_api(prompt: str, max_retries=5) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.005},
    }
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending Gemini API request (attempt {attempt + 1}): {prompt[:100]}...")
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Gemini API response: {json.dumps(data, indent=2)[:500]}...")
            if not data.get("candidates") or not data["candidates"][0].get("content") or not data["candidates"][0]["content"].get("parts"):
                logger.error("Invalid API response structure")
                return "Error processing the API response. Please try again or contact info@kmit.in."
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return "Failed to get a response from the API after multiple attempts. Please try again later or contact info@kmit.in."
        except (KeyError, IndexError) as e:
            logger.error(f"Gemini API parsing error: {e}")
            return "Error processing the API response. Please try again or contact info@kmit.in."
    return "Unexpected error in API call."

# Query model
class QueryModel(BaseModel):
    query: str

# Distance query model
class DistanceQueryModel(BaseModel):
    location: str

GREETINGS = {"hi", "hello", "hey", "greetings"}

# Search documents
def hybrid_search(query: str, category: str, k: int = 50) -> List[Document]:
    query_lower = query.lower()
    expanded_query = query_lower
    category_keywords = {
        "Admissions": ["admission", "eligibility", "eapcet", "ecet", "fees", "seat", "tuition", "contact", "scholarship"],
        "Courses": ["course", "btech", "cse", "csm", "data science", "it", "intake"],
        "Faculty": ["faculty", "hod", "professor", "assistant", "phd", "mtech"],
        "Exams & Regulations": ["exam", "schedule", "syllabus", "regulation", "autonomous", "kr24", "kr23"],
        "Placements": ["placement", "salary", "package", "company", "offer", "ctc", "job", "internship"],
        "Campus Facilities": ["facility", "library", "sport", "gym", "auditorium", "badminton", "football", "hostel", "lab"],
        "Administration": ["administration", "principal", "location", "department", "founder", "ranking", "timing"]
    }
    # Boost placement statistics over internships
    if category == "Placements":
        expanded_query += " placement statistics students placed average ctc highest ctc companies visited"
    if category in category_keywords:
        expanded_query += f" {' '.join(category_keywords[category])}"
    all_keywords = [kw for keywords in category_keywords.values() for kw in keywords]
    query_words = query_lower.split()
    for word in query_words:
        if len(word) > 2:
            best_match = process.extractOne(word, all_keywords, score_cutoff=50)
            if best_match:
                matched_word, score = best_match[0], best_match[1]
                expanded_query += f" {matched_word}"
                logger.info(f"Fuzzy match for '{word}': '{matched_word}' (score: {score})")
            else:
                logger.info(f"No fuzzy match for '{word}'")
    try:
        results = vectordb.similarity_search(expanded_query, k=k, filter={"category": category})
        logger.info(f"Search '{query}' (expanded: '{expanded_query[:100]}...'): {len(results)} results")
        for doc in results[:3]:
            logger.info(f"Result: source={doc.metadata.get('source')}, category={doc.metadata.get('category')}, content={doc.page_content[:100]}...")
        if not results:
            logger.warning(f"No results for category '{category}', falling back to all documents")
            results = vectordb.similarity_search(expanded_query, k=k)
            logger.info(f"Fallback search returned {len(results)} results")
            for doc in results[:3]:
                logger.info(f"Fallback result: source={doc.metadata.get('source')}, category={doc.metadata.get('category')}, content={doc.page_content[:100]}...")
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# Extract answer
def extract_answer(query: str, results: List[Document]) -> str:
    if not results:
        logger.warning("No search results found")
        return "I don’t have enough information to answer this. Please contact info@kmit.in."
    full_context = "\n".join(doc.page_content for doc in results)
    if not full_context.strip():
        logger.warning("Empty context")
        return "I don’t have enough information to answer this. Please contact info@kmit.in."
    context_lines = full_context.count("\n") + 1
    logger.info(f"Full context: {full_context[:500]}... ({context_lines} lines)")
    prompt = f"""
    You are a KMIT chatbot using RAG with Gemini AI. Answer the query: '{query}' using only the provided context. Compile ALL relevant information in a clear, structured markdown format (use **bold**, * lists, # headings). For 'Placements', prioritize placement statistics (e.g., number of students placed, average CTC, highest CTC, companies visited) over internship data unless internships are specifically requested. Include every detail related to the query, even if sparse or scattered. For queries like 'admissions', 'placements', or 'campus facilities', summarize ALL applicable data (e.g., eligibility, fees, placement stats, facilities list). Do not invent or generalize beyond the context. If no relevant data is found, return: 'I don’t have enough information to answer this. Please contact info@kmit.in.' Structure the answer by categories (e.g., Admissions, Courses, Faculty, etc.).
    Context:
    {full_context}
    Answer:
    """
    logger.info(f"Processing query: {query} with context from {len(results)} documents")
    return call_gemini_api(prompt)

@app.post("/query/")
async def fetch_answer(request: QueryModel):
    query_text = request.query.strip().lower()
    logger.info(f"Received query: {query_text}")

    try:
        category = "General"
        categories = {
            "admissions": ("Admissions", ["admission", "eligibility", "eapcet", "ecet", "fees", "seat", "tuition", "contact", "scholarship"]),
            "courses": ("Courses", ["course", "btech", "cse", "csm", "it", "data science", "intake"]),
            "faculty": ("Faculty", ["faculty", "hod", "professor", "assistant", "phd", "mtech"]),
            "exams": ("Exams & Regulations", ["exam", "regulation", "syllabus", "kr24", "kr23", "autonomous"]),
            "placements": ("Placements", ["placement", "salary", "job", "company", "ctc", "offers", "internship"]),
            "facilities": ("Campus Facilities", ["library", "sports", "gym", "auditorium", "badminton", "football", "hostel", "facility", "lab"]),
            "administration": ("Administration", ["principal", "founder", "timing", "blocks", "ranking", "where", "what", "administration"])
        }
        query_words = query_text.split()
        best_category = None
        highest_score = 0
        for key, (cat, keywords) in categories.items():
            for word in query_words:
                if len(word) > 2:
                    best_match = process.extractOne(word, keywords, score_cutoff=50)
                    if best_match and best_match[1] > highest_score:
                        highest_score = best_match[1]
                        best_category = key
                        logger.info(f"Fuzzy match for '{word}' in category '{cat}': '{best_match[0]}' (score: {best_match[1]})")
        if best_category:
            category = categories[best_category][0]
        logger.info(f"Detected category: {category}")

        if query_text in GREETINGS:
            logger.info("Returning greeting response")
            return {
                "answer": "Hello! I’m your KMIT chatbot. Ask me about admissions, courses, faculty, exams, placements, campus facilities, administration, or calculate distance from KMIT to any location in India!"
            }

        results = hybrid_search(query_text, category)
        logger.info(f"Search returned {len(results)} documents")
        if not results:
            logger.warning(f"No results for query: {query_text}")
            return {"answer": "I don’t have enough information to answer this. Please contact info@kmit.in."}

        answer = extract_answer(request.query, results)
        logger.info(f"Generated answer: {answer[:200]}...")
        return {"answer": answer}

    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        return {"answer": f"Sorry, something went wrong: {str(e)}. Please try again or contact info@kmit.in."}

@app.post("/distance/")
async def calculate_distance(request: DistanceQueryModel):
    location = request.location.strip()
    logger.info(f"Received distance query for location: {location}")

    try:
        if not location or len(location) < 3:
            logger.warning(f"Invalid location input: {location}")
            return {"answer": "Please provide a valid location (e.g., city name, address, or landmark in India)."}

        coords = geocode_address(location)
        logger.info(f"Geocoded {location} to coords: {coords}")
        if not coords:
            logger.warning(f"Could not geocode location: {location}")
            return {
                "answer": f"Could not find coordinates for '{location}'. Please provide a valid address, city, or landmark in India (e.g., 'Delhi', 'MG Road, Bangalore')."
            }

        distance = haversine_distance(KMIT_COORDS[0], KMIT_COORDS[1], coords[0], coords[1])
        travel_time_hours = distance / 60.0
        hours = int(travel_time_hours)
        minutes = int((travel_time_hours - hours) * 60)
        travel_time_str = f"{hours} hours and {minutes} minutes" if hours > 0 else f"{minutes} minutes"

        google_maps_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&origin={coords[0]},{coords[1]}"
            f"&destination={KMIT_COORDS[0]},{KMIT_COORDS[1]}"
            f"&travelmode=driving"
        )

        logger.info(f"Calculated distance from KMIT to {location}: {distance:.2f} km, travel time: {travel_time_str}")
        return {
            "answer": (
                f"The distance from KMIT (Narayanguda, Hyderabad) to {location} is approximately **{distance:.2f} kilometers**.\n"
                f"Estimated travel time by car (assuming 60 km/h): **{travel_time_str}**.\n\n"
                f"**Get Directions**: [Click here for Google Maps directions to KMIT]({google_maps_url})"
            )
        }

    except Exception as e:
        logger.error(f"Distance calculation error: {str(e)}")
        return {
            "answer": f"Sorry, something went wrong while calculating distance: {str(e)}. Please try again or contact info@kmit.in."
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "documents_loaded": vectordb._collection.count()}

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise