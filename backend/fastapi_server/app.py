import os
from dotenv import load_dotenv
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
from main import record_audio, convert_to_16khz_mono, transcribe_with_google  # Import from main.py

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="KMIT Chatbot",
              description="Chatbot for KMIT queries using RAG with Gemini AI and distance calculation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5500",
                   "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Directories and constants
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kmit_data")
PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PERSIST_DIR, exist_ok=True)

KMIT_COORDS = (17.4045, 78.4948)
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

def check_disk_space(path):
    disk = psutil.disk_usage(path)
    free_mb = disk.free / (1024 * 1024)
    logger.info(f"Disk space at {path}: {free_mb:.2f} MB free")
    if free_mb < 100:
        logger.warning(f"Low disk space at {path}: {free_mb:.2f} MB free")
    return free_mb

check_disk_space(os.path.dirname(PERSIST_DIR))

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

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

def process_json(data: Dict, filename: str, chunk_size=500) -> List[Dict]:
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
    try:
        raw_data = json.dumps(data, indent=2)
        logger.info(f"Processing {filename}: {raw_data[:500]}...")
        flat_content = flatten(data)
        full_text = "\n".join(flat_content)
        if not full_text.strip():
            logger.warning(f"No content extracted from {filename}")
            return []

        lines = full_text.split("\n")
        chunks = []
        current_chunk = []
        current_length = 0
        section_keys = ["Cutoff_Ranks", "Fee_Structure", "Student_Strength", "Placements", "Student_Life",
                        "Hostel_Facilities", "Events", "Academic_and_Disciplinary", "Faculty", "Teaching_Methods",
                        "Curriculum_Focus", "Extracurriculars", "Anti_Ragging", "College_Timings",
                        "Counseling_and_Mental_Health"]
        for line in lines:
            line_length = len(line.split())
            is_section_start = any(line.startswith(f"KMIT.{key}") for key in section_keys)
            if (current_length + line_length > chunk_size or is_section_start) and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        for chunk in chunks:
            items.append({"fields": [chunk], "raw": data})
        logger.info(f"Extracted {len(items)} chunks from {filename}")
        return items
    except Exception as e:
        logger.error(f"Error processing {filename}: {e}")
        return []

documents = []
json_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
if not json_files:
    logger.warning(f"No JSON files found in {DATA_DIR}. Starting server without data. Queries will return limited responses.")
else:
    for filename in json_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                fn_lower = filename.lower()
                category = "General"
                content_keys = json.dumps(data).lower()
                if "faq" in fn_lower or "admissions" in fn_lower or "eapcet" in fn_lower or "ecet" in fn_lower or "cutoff" in content_keys:
                    category = "Admissions"
                elif "placements" in fn_lower or "placement" in content_keys:
                    category = "Placements"
                elif "faculty" in fn_lower or "hods" in fn_lower or "faculty" in content_keys:
                    category = "Faculty"
                elif "infrastructure" in fn_lower or "facilities" in fn_lower or "sports" in fn_lower or "library" in fn_lower or "hostel" in content_keys:
                    category = "Campus Facilities"
                elif "regulations" in fn_lower or "autonomous" in fn_lower or "regulation" in content_keys:
                    category = "Exams & Regulations"
                elif "courses" in fn_lower or "syllabi" in fn_lower or "vas" in fn_lower or "departments" in content_keys:
                    category = "Courses"
                elif "generalinfo" in fn_lower or "administration" in fn_lower or "timings" in content_keys or "anti_ragging" in content_keys:
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
                    keywords += f" {category.lower()} kmit {filename.lower().replace('.json', '')} {category.replace(' & ', ' ').replace('Exams', 'exam').replace('Regulations', 'regulation')}"
                    metadata = {
                        "source": filename,
                        "category": category,
                        "keywords": keywords,
                        "raw_data": json.dumps(group["raw"]),
                    }
                    documents.append(Document(page_content=content, metadata=metadata))
                    logger.info(f"Created document from {filename}: category={category}, content={content[:100]}...")
                logger.info(f"Loaded {filename}: {len(groups)} chunks, category={category}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filename}: {e}")
        except Exception as e:
            logger.error(f"Error in {filename}: {e}")

if not documents:
    logger.warning("No documents loaded! Queries will return limited responses.")

embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
vectordb = None
try:
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        logger.info(f"Cleared existing ChromaDB at {PERSIST_DIR}")
    os.makedirs(PERSIST_DIR, exist_ok=True)
    unique_collection = f"kmit_{int(time.time())}"
    vectordb = Chroma.from_documents(documents, embedding, persist_directory=PERSIST_DIR,
                                     collection_name=unique_collection)
    logger.info(f"Created new collection '{unique_collection}' with {len(documents)} documents")
except Exception as e:
    logger.error(f"ChromaDB creation failed: {e}")
    raise RuntimeError("Failed to initialize ChromaDB")

logger.info(f"ChromaDB: {vectordb._collection.count()} documents")
if vectordb._collection.count() == 0:
    logger.error("Failed to index documents!")
    raise RuntimeError("ChromaDB indexing failed")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise RuntimeError("GEMINI_API_KEY is required")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def call_gemini_api(prompt: str, max_retries=5) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.1},
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

class QueryModel(BaseModel):
    query: str

class DistanceQueryModel(BaseModel):
    location: str

class STTRequestModel(BaseModel):
    record_seconds: int = 4  # Default to 4 seconds, as in main.py

class STTResponse(BaseModel):
    success: bool
    transcription: str
    chatbot_response: str

GREETINGS = {"hi", "hello", "hey", "greetings"}

def hybrid_search(query: str, category: str, k: int = 100) -> List[Document]:
    query_lower = query.lower()
    expanded_query = query_lower
    category_keywords = {
        "Admissions": ["admission", "eligibility", "eapcet", "ecet", "fees", "seat", "tuition", "contact",
                       "scholarship", "cutoff", "ranks"],
        "Courses": ["course", "btech", "cse", "csm", "data science", "it", "intake", "sections", "students"],
        "Faculty": ["faculty", "hod", "professor", "assistant", "associate", "phd", "mtech", "incharge",
                    "qualification"],
        "Exams & Regulations": ["exam", "schedule", "syllabus", "regulation", "autonomous", "kr24", "kr23"],
        "Placements": ["placement", "salary", "package", "company", "offer", "ctc", "job", "internship", "placed",
                       "statistics"],
        "Campus Facilities": ["library", "sports", "gym", "auditorium", "badminton", "football", "hostel", "lab",
                              "campus", "area"],
        "Administration": ["administration", "principal", "founder", "location", "department", "ranking", "timing",
                           "anti-ragging", "mental health"]
    }
    department_keywords = ["cse", "computer science", "ai & ml", "data science", "it", "information technology"]
    expanded_query += " " + " ".join(department_keywords)

    if category in category_keywords:
        expanded_query += f" {' '.join(category_keywords[category])}"
    all_keywords = [kw for keywords in category_keywords.values() for kw in keywords] + department_keywords
    query_words = query_lower.split()
    for word in query_words:
        if len(word) > 2:
            best_match = process.extractOne(word, all_keywords, score_cutoff=80)
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
            logger.info(
                f"Result: source={doc.metadata.get('source')}, category={doc.metadata.get('category')}, content={doc.page_content[:100]}...")

        if len(results) < 5:
            logger.warning(f"Low results ({len(results)}) for category '{category}', falling back to all documents")
            all_results = vectordb.similarity_search(expanded_query, k=k)
            seen = set(doc.page_content for doc in results)
            results.extend([doc for doc in all_results if doc.page_content not in seen])
            logger.info(f"Fallback search returned {len(all_results)} results, total unique: {len(results)}")
            for doc in results[:3]:
                logger.info(
                    f"Fallback result: source={doc.metadata.get('source')}, category={doc.metadata.get('category')}, content={doc.page_content[:100]}...")

        results = results[:k]
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

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
    You are a KMIT chatbot using RAG with Gemini AI. Answer the query: '{query}' using only the provided context. Compile ALL relevant information in a clear, structured markdown format (use **bold**, * lists, # headings). For 'Placements', prioritize placement statistics (e.g., number of students placed, average CTC, highest CTC, companies visited) over internship data unless internships are specifically requested. For 'Faculty', include names, roles, and qualifications where relevant. For 'Admissions', include cutoff ranks, fees, and scholarships. For 'Courses', detail departments, intake, and sections. Include every detail related to the query, even if sparse or scattered. If no relevant data is found, return: 'I don’t have enough information to answer this. Please contact info@kmit.in.' Structure the answer by categories (e.g., Admissions, Courses, Faculty, etc.). Do not invent or generalize beyond the context. Ensure answers are precise, concise, and directly address the query.
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
            "admissions": ("Admissions",
                           ["admission", "eligibility", "eapcet", "ecet", "fees", "seat", "tuition", "contact",
                            "scholarship", "cutoff", "ranks"]),
            "courses": ("Courses",
                        ["course", "btech", "cse", "csm", "it", "data science", "intake", "sections", "students"]),
            "faculty": ("Faculty", ["faculty", "hod", "professor", "assistant", "associate", "phd", "mtech", "incharge",
                                    "qualification"]),
            "exams": ("Exams & Regulations", ["exam", "regulation", "syllabus", "kr24", "kr23", "autonomous"]),
            "placements": ("Placements",
                           ["placement", "salary", "job", "company", "ctc", "offers", "internship", "placed",
                            "statistics"]),
            "facilities": ("Campus Facilities",
                           ["library", "sports", "gym", "auditorium", "badminton", "football", "hostel", "lab",
                            "campus", "area"]),
            "administration": ("Administration",
                               ["principal", "founder", "timing", "blocks", "ranking", "where", "what",
                                "administration", "anti-ragging", "mental health"])
        }
        query_words = query_text.split()
        best_category = None
        highest_score = 0
        for key, (cat, keywords) in categories.items():
            for word in query_words:
                if len(word) > 2:
                    best_match = process.extractOne(word, keywords, score_cutoff=80)
                    if best_match and best_match[1] > highest_score:
                        highest_score = best_match[1]
                        best_category = key
                        logger.info(
                            f"Fuzzy match for '{word}' in category '{cat}': '{best_match[0]}' (score: {best_match[1]})")
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

@app.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(request: STTRequestModel):
    try:
        logger.info(f"Starting audio recording for {request.record_seconds} seconds...")
        record_audio(record_seconds=request.record_seconds)
        logger.info("Recording complete, converting audio...")
        convert_to_16khz_mono()
        logger.info("Conversion complete, transcribing...")
        transcription = transcribe_with_google()
        logger.info(f"Transcription: {transcription}")

        if transcription and transcription != "No speech detected":
            query_response = await fetch_answer(QueryModel(query=transcription))
            chatbot_response = query_response["answer"]
            success = True
        else:
            transcription = transcription or "No speech detected"
            chatbot_response = "No speech detected. Please try again."
            success = False

        return {
            "success": success,
            "transcription": transcription,
            "chatbot_response": chatbot_response
        }
    except Exception as e:
        logger.error(f"STT error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "transcription": "Error occurred",
            "chatbot_response": f"Error during transcription: {str(e)}. Please try again."
        }
    finally:
        for file in ["raw_audio.wav", "converted.wav"]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    logger.info(f"Removed temporary file: {file}")
                except Exception as e:
                    logger.error(f"Failed to remove {file}: {e}")

if __name__ == "__main__":
    import uvicorn
    try:
        port = int(os.getenv("PORT", 8001))
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise