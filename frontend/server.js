const express = require('express');
const path = require('path');
const mongoose = require('mongoose');
const axios = require('axios');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const { checkForAuthenticationCookie } = require('./middleware/authentication'); // Updated path
const userRouter = require('./routes/userRoute'); // Updated path
require('dotenv').config(); // Import and configure dotenv

const PORT = process.env.PORT || 8000; // Allow Render to set PORT
const app = express();

// MongoDB Connection
const MONGODB_URI = process.env.MONGODB_URI;
if (!MONGODB_URI) {
    console.error('❌ MONGODB_URI not found in environment variables');
    process.exit(1);
}

mongoose.connect(MONGODB_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true
})
    .then(() => console.log('✅ MongoDB connected'))
    .catch((err) => {
        console.error('❌ MongoDB connection error (proceeding without DB):', err.message);
    });

mongoose.connection.on('connected', () => console.log('✅ Mongoose connected'));
mongoose.connection.on('error', (err) => console.error('❌ Mongoose error:', err.message));
mongoose.connection.on('disconnected', () => console.log('⚠ Mongoose disconnected'));

// App Configuration
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(cors({ origin: '*', credentials: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(checkForAuthenticationCookie('token'));

// Proxy Routes for Chatbot
const FASTAPI_BACKEND_URL = process.env.FASTAPI_BACKEND_URL || 'http://localhost:8001';
app.post('/chat/query', async (req, res) => {
    try {
        console.log('Received /chat/query request:', req.body);
        const response = await axios.post(`${FASTAPI_BACKEND_URL}/query/`, req.body, {
            headers: { 'Content-Type': 'application/json' }
        });
        console.log('FastAPI /query response:', response.data);
        res.json(response.data);
    } catch (error) {
        console.error('Proxy error (/chat/query):', error.message);
        res.status(500).json({ answer: `Sorry, something went wrong: ${error.message}. Please try again or contact info@kmit.in.` });
    }
});

app.post('/chat/distance', async (req, res) => {
    try {
        console.log('Received /chat/distance request:', req.body);
        const response = await axios.post(`${FASTAPI_BACKEND_URL}/distance/`, req.body, {
            headers: { 'Content-Type': 'application/json' }
        });
        console.log('FastAPI /distance response:', response.data);
        res.json(response.data);
    } catch (error) {
        console.error('Proxy error (/chat/distance):', error.message);
        res.status(500).json({ answer: `Sorry, something went wrong: ${error.message}. Please try again or contact info@kmit.in.` });
    }
});

// Routes
app.use('/', userRouter);

app.get('/', (req, res) => {
    console.log('Rendering home page');
    res.render('home');
});

// Start Server
app.listen(PORT, () => console.log(`🚀 Server running at http://localhost:${PORT}`));