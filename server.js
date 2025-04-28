require('dotenv').config();
const express = require('express');
const path = require('path');
const mongoose = require('mongoose');
const cookieParser = require('cookie-parser');
const cors = require('cors');
const axios = require('axios');
const logger = require('winston');
const { checkForAuthenticationCookie } = require('./middleware/authentication');
const userRouter = require('./routes/userRoute');
const { ChromaClient } = require('chromadb');
const { execSync } = require('child_process');
const fs = require('fs').promises; // For JSON fallback

// Constants
const PORT = 3000;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent';
const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';
const OSRM_URL = 'http://router.project-osrm.org/route/v1/driving/';
const KMIT_ADDRESS = 'Keshav Memorial Institute of Technology, Narayanguda, Hyderabad, Telangana, India';
const KMIT_FALLBACK_ADDRESS = 'Narayanguda, Hyderabad, Telangana, India';
const USER_AGENT = 'KMIT-Chatbot/1.0 (contact: info@kmit.in)';
const HYDERABAD_LOCALITIES = [
  'banjara hills', 'uppal', 'madhapur', 'gachibowli', 'hitech city', 'kukatpally', 'secunderabad',
  'ameerpet', 'begumpet', 'jubilee hills', 'somajiguda', 'dilsukhnagar', 'lb nagar', 'miyapur'
].map(loc => loc.toLowerCase());
const CHROMA_HOST = 'localhost';
const CHROMA_PORT = 8000;
const COLLECTION_NAME = 'kmit_data';
const CHUNK_SIZE = 200;
const CHROMA_MAX_RETRIES = 3;
const CHROMA_RETRY_DELAY = 2000;
const BYPASS_CHROMADB = process.env.BYPASS_CHROMADB === 'true' || false;

// Initialize Express
const app = express();

// Logger Setup
const log = logger.createLogger({
  level: 'info',
  format: logger.format.combine(logger.format.timestamp(), logger.format.json()),
  transports: [
    new logger.transports.Console(),
    new logger.transports.File({ filename: 'app.log' })
  ]
});

// MongoDB Connection
mongoose.connect('mongodb://127.0.0.1:27017/chatbot')
  .then(() => log.info('✅ MongoDB connected'))
  .catch(err => log.error('❌ MongoDB connection error (proceeding without DB):', err.message));

mongoose.connection.on('connected', () => log.info('✅ Mongoose connected'));
mongoose.connection.on('error', err => log.error('❌ Mongoose error:', err));
mongoose.connection.on('disconnected', () => log.warn('⚠️ Mongoose disconnected'));

// Location Cache Schema
const LocationSchema = new mongoose.Schema({
  address: { type: String, unique: true },
  lat: Number,
  lon: Number,
  lastUpdated: { type: Date, default: Date.now }
});
const Location = mongoose.model('Location', LocationSchema);

// ChromaDB Setup
const chromaClient = new ChromaClient({ path: `http://${CHROMA_HOST}:${CHROMA_PORT}` });
let collection;
let chromaInitialized = false;

async function initializeChroma() {
  if (BYPASS_CHROMADB) {
    log.info('ChromaDB initialization bypassed (BYPASS_CHROMADB=true). Using JSON fallback.');
    chromaInitialized = false;
    return;
  }

  try {
    execSync('chroma --version', { stdio: 'ignore' });
    log.info('Chroma command found in system PATH.');
  } catch (e) {
    log.warn('Chroma command not found. Ensure ChromaDB is installed (`pip install chromadb`) and Python Scripts directory is in PATH (e.g., `C:\\Users\\sabav\\AppData\\Local\\Programs\\Python\\Python39\\Scripts`).');
  }

  try {
    log.info(`Checking ChromaDB server at http://${CHROMA_HOST}:${CHROMA_PORT}`);
    await axios.head(`http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1`, { timeout: 3000 });
    for (let attempt = 1; attempt <= CHROMA_MAX_RETRIES; attempt++) {
      try {
        log.info(`Attempting ChromaDB connection (attempt ${attempt}/${CHROMA_MAX_RETRIES})`);
        const heartbeat = await axios.get(`http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/heartbeat`, { timeout: 5000 });
        log.info(`ChromaDB heartbeat response: ${JSON.stringify(heartbeat.data)}`);
        collection = await chromaClient.getOrCreateCollection({ name: COLLECTION_NAME });
        chromaInitialized = true;
        log.info(`✅ ChromaDB collection '${COLLECTION_NAME}' initialized`);
        return;
      } catch (e) {
        log.error(`ChromaDB attempt ${attempt} failed: ${e.message}`);
        if (attempt < CHROMA_MAX_RETRIES) {
          log.info(`Retrying in ${CHROMA_RETRY_DELAY}ms...`);
          await new Promise(resolve => setTimeout(resolve, CHROMA_RETRY_DELAY));
        }
      }
    }
    log.warn('ChromaDB unavailable. Using JSON fallback.');
    chromaInitialized = false;
  } catch (e) {
    log.error(`ChromaDB pre-check failed: ${e.message}`);
    log.warn('Bypassing ChromaDB. Ensure ChromaDB is running: `chroma run --host localhost --port 8000`. Using JSON fallback.');
    chromaInitialized = false;
  }
}

// Middleware Configuration
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(cors({ origin: 'http://localhost:3000' }));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(checkForAuthenticationCookie('token'));
app.use(express.static(path.join(__dirname, 'public')));

// Routes
app.use('/', userRouter);

app.get('/', (req, res) => {
  if (req.user) {
    return res.redirect('/chat');
  }
  return res.redirect('/signin');
});

// Utility Functions
function formatLocation(location) {
  return location
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\s+/g, ' ');
}

function getGeocodingContext(location) {
  const lowerLocation = location.toLowerCase();
  if (HYDERABAD_LOCALITIES.some(loc => lowerLocation.includes(loc))) {
    return `${location}, Hyderabad, Telangana, India`;
  }
  return `${location}, Telangana, India`;
}

function cleanText(text) {
  return text
    .replace(/[^\w\s.,-]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function chunkText(text, chunkSize = CHUNK_SIZE) {
  const words = text.split(/\s+/);
  const chunks = [];
  for (let i = 0; i < words.length; i += chunkSize) {
    const chunk = cleanText(words.slice(i, i + chunkSize).join(' '));
    if (chunk.length > 20) chunks.push(chunk);
  }
  return chunks;
}

// API Calls
async function callGeminiApi(prompt, maxRetries = 3) {
  if (!GEMINI_API_KEY) {
    log.error('Gemini API key missing. Set GEMINI_API_KEY in .env file.');
    return 'API key missing. Please contact info@kmit.in.';
  }
  const headers = { 'Content-Type': 'application/json' };
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { maxOutputTokens: 4000, temperature: 0.0 }
  };
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await axios.post(`${GEMINI_API_URL}?key=${GEMINI_API_KEY}`, payload, { headers, timeout: 25000 });
      const text = response.data.candidates[0]?.content?.parts[0]?.text?.trim();
      if (!text) throw new Error('No valid response from API');
      return text;
    } catch (e) {
      log.error(`Gemini API attempt ${attempt + 1} failed: ${e.message}`);
      if (attempt < maxRetries - 1) await new Promise(resolve => setTimeout(resolve, 2 ** attempt * 1000));
      else return `API error after ${maxRetries} attempts: ${e.message}. Please try again later.`;
    }
  }
  return 'Unexpected error in API call.';
}

async function geocodeAddress(address, maxRetries = 3) {
  const cached = await Location.findOne({ address });
  if (cached && (Date.now() - cached.lastUpdated) < 30 * 24 * 60 * 60 * 1000) {
    log.info(`Cache hit for ${address}`);
    return { lat: cached.lat, lon: cached.lon };
  }

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await axios.get(NOMINATIM_URL, {
        params: { q: address, format: 'json', limit: 1, addressdetails: 1 },
        headers: { 'User-Agent': USER_AGENT },
        timeout: 10000
      });
      log.info(`Nominatim response for ${address}: ${JSON.stringify(response.data)}`);
      const coords = response.data[0];
      if (coords && coords.lat && coords.lon && coords.address?.country === 'India') {
        await Location.findOneAndUpdate(
          { address },
          { address, lat: coords.lat, lon: coords.lon, lastUpdated: Date.now() },
          { upsert: true }
        );
        return { lat: coords.lat, lon: coords.lon };
      }
      log.warn(`No valid geocoding results for ${address}`);
      return null;
    } catch (e) {
      log.error(`Geocoding attempt ${attempt + 1} failed for ${address}: ${e.message}`);
      if (attempt < maxRetries - 1) await new Promise(resolve => setTimeout(resolve, (2 ** attempt * 1000) + 1000));
    }
  }
  return null;
}

async function calculateDistance(userLocation) {
  try {
    const formattedLocation = formatLocation(userLocation);
    const contextLocation = getGeocodingContext(formattedLocation);
    const districtLocation = formattedLocation.toLowerCase().includes('district')
      ? `${formattedLocation.replace(/district/i, '').trim()} District, Telangana, India`
      : `${formattedLocation} town, Telangana, India`;

    let kmitCoords = await geocodeAddress(KMIT_ADDRESS);
    if (!kmitCoords) {
      log.warn(`Primary KMIT address failed, trying fallback: ${KMIT_FALLBACK_ADDRESS}`);
      kmitCoords = await geocodeAddress(KMIT_FALLBACK_ADDRESS);
    }
    if (!kmitCoords) {
      log.error('Failed to geocode KMIT address');
      return 'Could not find KMIT location. Please try again or contact info@kmit.in.';
    }

    let userCoords = await geocodeAddress(contextLocation);
    if (!userCoords) {
      log.warn(`Context location failed, trying raw: ${formattedLocation}`);
      userCoords = await geocodeAddress(formattedLocation);
    }
    if (!userCoords) {
      log.warn(`Raw location failed, trying district/town: ${districtLocation}`);
      userCoords = await geocodeAddress(districtLocation);
    }
    if (!userCoords) {
      log.error(`Failed to geocode user location: ${userLocation}`);
      return `Could not find the location "${userLocation}". Please check the spelling or provide a more specific address (e.g., "Nalgonda, Telangana").`;
    }

    const osrmUrl = `${OSRM_URL}${kmitCoords.lon},${kmitCoords.lat};${userCoords.lon},${userCoords.lat}?overview=false`;
    const distanceApi = await axios.get(osrmUrl, { timeout: 10000 });
    const distanceMeters = distanceApi.data.routes[0]?.distance || 0;
    const durationSeconds = distanceApi.data.routes[0]?.duration || 0;

    if (!distanceMeters || !durationSeconds) {
      log.error('OSRM returned no valid data');
      return 'Unable to calculate distance. Please try again or contact info@kmit.in.';
    }

    const distanceKm = (distanceMeters / 1000).toFixed(1);
    const durationMin = Math.round(durationSeconds / 60);

    const prompt = `
You are a KMIT chatbot. The driving distance between Keshav Memorial Institute of Technology (Narayanguda, Hyderabad, Telangana, India) and ${formattedLocation} is ${distanceKm} km, and it takes ${durationMin} minutes. Provide a concise response with:
- KMIT's full address
- The exact distance and duration
- Contact email: info@kmit.in
Do not add extra information.
    `;
    return await callGeminiApi(prompt);
  } catch (e) {
    log.error(`Distance calculation error: ${e.message}`);
    return `Error calculating distance: ${e.message}. Please try again or contact info@kmit.in.`;
  }
}

// ChromaDB Search
async function searchChromaDB(query, category, limit = 15) {
  if (!chromaInitialized) {
    log.warn('ChromaDB not initialized. Skipping search.');
    return [];
  }
  try {
    const queryText = cleanText(query);
    const results = await collection.query({
      query_texts: [queryText],
      n_results: limit,
      where: category !== 'General' ? { category: category } : undefined,
      include: ['documents', 'metadatas']
    });
    const documents = results.documents[0].map((doc, i) => ({
      content: doc,
      metadata: results.metadatas[0][i]
    }));
    log.info(`ChromaDB search for '${query}' (category: ${category}): ${documents.length} results`);
    return documents;
  } catch (e) {
    log.error(`ChromaDB search failed: ${e.message}`);
    return [];
  }
}

// Answer Extraction
async function extractAnswer(query, results) {
  const queryText = cleanText(query);
  if (!chromaInitialized || !results.length) {
    log.warn(`No ChromaDB results or initialization failed for query: ${query}`);
    const category = queryText.toLowerCase().includes('admissions') ? 'Admissions' :
                    queryText.toLowerCase().includes('placements') ? 'Placements' :
                    queryText.toLowerCase().includes('facilities') ? 'Campus Facilities' :
                    queryText.toLowerCase().includes('courses') ? 'Courses' :
                    queryText.toLowerCase().includes('faculty') ? 'Faculty' :
                    queryText.toLowerCase().includes('exams') ? 'Exams' : 'General';

    // Try JSON fallback
    try {
      const jsonPath = path.join(__dirname, 'kmit_data.json');
      const jsonData = JSON.parse(await fs.readFile(jsonPath, 'utf8'));
      const filteredData = jsonData.filter(item => item.category === category);
      if (filteredData.length) {
        const context = filteredData.map(item => ({
          content: item.content,
          source: item.source || 'KMIT Data',
          category: item.category,
          raw_data: '{}'
        }));
        const prompt = `
You are a KMIT chatbot using Retrieval-Augmented Generation (RAG). Answer the query: '${queryText}' using ONLY the provided context. Follow these rules:
1. Use ALL relevant information from the context.
2. Do NOT invent or generalize beyond the context.
3. Use headings (e.g., 'Admissions at KMIT') and bullet points.
4. Include contact email info@kmit.in.
Context:
${JSON.stringify(context, null, 2)}
Answer:
        `;
        const answer = await callGeminiApi(prompt);
        log.info(`JSON fallback response for '${query}': ${answer}`);
        return answer;
      }
    } catch (e) {
      log.warn(`JSON fallback failed: ${e.message}`);
    }

    // Gemini API fallback
    const prompt = `
Welcome to VIDYASAARATHI, your KMIT chatbot! The query is: '${queryText}'. Due to a temporary database issue, I can only provide general information about ${category} at KMIT:
- Admissions: Requires 10+2 (PCM) and EAPCET rank; apply via TS EAPCET counseling or management quota.
- Placements: Campus drives with companies like TCS, Infosys; includes coding and soft skills training.
- Campus Facilities: Offers library, labs, sports, and hostels.
- Courses: B.Tech in CSE, ECE, and other branches.
- Faculty: Qualified with Ph.D./M.Tech degrees.
- Exams: JNTUH-affiliated semester exams.
For details, contact info@kmit.in or visit www.kmit.in. (Under 80 words)
    `;
    const answer = await callGeminiApi(prompt);
    log.info(`Gemini API fallback response for '${query}': ${answer}`);
    return answer;
  }

  const context = results.map(doc => ({
    content: doc.content,
    source: doc.metadata.source || 'unknown',
    category: doc.metadata.category || 'General',
    raw_data: doc.metadata.raw_data || '{}'
  }));

  const prompt = `
You are a KMIT chatbot using Retrieval-Augmented Generation (RAG) with Transformer models. Your goal is to provide a comprehensive, accurate, and structured response to the query: '${queryText}' using ONLY the provided context from ChromaDB, which contains college-related documents (FAQs, syllabi, notices). Follow these strict rules:
1. Extract ALL relevant information from the context, including details from 'content' and 'raw_data' fields.
2. Do NOT invent, generalize, or assume any information not explicitly present in the context.
3. If the context lacks sufficient information, return: 'I don’t have enough information to answer this completely. Please contact info@kmit.in or visit www.kmit.in.'
4. Organize the response with clear headings (e.g., 'Admissions at KMIT', 'Faculty Details') and bullet points for readability.
5. Match the query to these categories and include ALL relevant data:
   - Admissions: Eligibility, entrance tests (EAPCET, ECET), seat allocation, lateral entry, fee structure, application process, contact.
   - Courses: Programs offered, intake, syllabus, curriculum, branches.
   - Placements: Companies, offers, salaries, internships, placement statistics by batch.
   - Campus Facilities: Library, sports, gym, auditorium, labs, timings, events.
   - Administration: Principal, location, departments, founder, ranking, contact, campus details.
6. For queries requesting "total details" or "all details," include every available piece of information from the context, even minor details.
7. For greeting queries (e.g., 'hi', 'hello'), provide a welcome message introducing the chatbot’s capabilities (e.g., answering queries about admissions, courses, etc.) and include the contact email info@kmit.in.
8. Include the contact email info@kmit.in in all responses for further inquiries.
Context:
${JSON.stringify(context, null, 2)}
Answer:
  `;
  const answer = await callGeminiApi(prompt);
  if (answer.includes('No valid response') || answer.includes('API error')) {
    log.error(`Gemini API failed for query: ${query}`);
    return 'I don’t have enough information to answer this completely. Please contact info@kmit.in or visit www.kmit.in.';
  }
  log.info(`Generated answer for '${query}': ${answer.slice(0, 100)}...`);
  return answer;
}

// Chatbot Routes
app.get('/chat', (req, res) => {
  res.render('home');
});

app.post('/query', async (req, res) => {
  const { query } = req.body;
  if (!query) return res.status(400).json({ error: 'Query is required' });
  log.info(`Received query: ${query}`);

  const queryText = cleanText(query.trim().toLowerCase());
  try {
    if (queryText.includes('distance') && queryText.includes('kmit')) {
      const locationMatch = queryText.match(/(?:distance\s*(?:from|to|between)\s*(?:kmit\s*(?:college)?|[\w\s,]+)\s*(?:to|and)\s*)([\w\s,]+)/i);
      const userLocation = locationMatch ? locationMatch[1].trim() : null;
      if (!userLocation) {
        const results = await searchChromaDB('distance query error', 'General');
        const answer = await extractAnswer('How to specify a location for distance calculation from KMIT', results);
        return res.json({ answer });
      }
      const answer = await calculateDistance(userLocation);
      return res.json({ answer });
    }

    if (queryText.includes('faq') || queryText.includes('faqs')) {
      const results = await searchChromaDB(queryText, 'General');
      const answer = await extractAnswer(query, results);
      return res.json({ answer });
    }

    let category = 'General';
    const categories = {
      admissions: ['admissions', 'fees', 'eapcet', 'ecet', 'eligibility', 'application', 'seat'],
      courses: ['courses', 'syllabus', 'curriculum', 'programs', 'btech'],
      faculty: ['faculty', 'hod', 'professors', 'teachers', 'department'],
      exams: ['exams', 'examinations', 'regulations', 'schedule'],
      placements: ['placements', 'salary', 'jobs', 'companies'],
      facilities: ['facilities', 'library', 'sports', 'gym', 'auditorium', 'labs'],
      administration: ['administration', 'principal', 'location', 'contact', 'ranking']
    };
    for (let key in categories) {
      if (categories[key].some(keyword => queryText.includes(keyword))) {
        category = key.charAt(0).toUpperCase() + key.slice(1);
        break;
      }
    }

    const results = await searchChromaDB(query, category);
    const answer = await extractAnswer(query, results);
    res.json({ answer });
  } catch (e) {
    log.error(`Query error: ${e.message}`);
    res.status(500).json({ answer: `Something went wrong: ${e.message}. Please try again or contact info@kmit.in.` });
  }
});

// Server Initialization
async function initialize() {
  if (!GEMINI_API_KEY) {
    log.warn('⚠️ GEMINI_API_KEY not set in .env. API calls will fail without a valid key.');
  }
  await initializeChroma();
  await Location.deleteMany({ address: { $regex: 'K.L. University', $options: 'i' } });
  await Location.deleteMany({
    address: {
      $in: [
        'Nalgonda, Hyderabad, Telangana, India',
        'Nalgonda District, Hyderabad, Telangana, India',
        'Devarakonda, Hyderabad, Telangana, India'
      ]
    }
  });
  log.info('Server initialized');
}

initialize().then(() => {
  app.listen(PORT, () => log.info(`🚀 Server running at http://localhost:${PORT}`));
}).catch(e => log.error(`Startup failed: ${e.message}`));