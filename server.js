const express = require('express');
const path = require('path');
const mongoose = require('mongoose');
const cookieParser = require('cookie-parser');
const cors = require('cors');
const { checkForAuthenticationCookie } = require('./middleware/authentication');
const userRouter = require('./routes/userRoute');
const chatRouter = require('./routes/chatRouter');

const PORT = 8000;
const app = express();

// MongoDB Connection (optional for now, keep if you plan to use it later)
mongoose.connect("mongodb://127.0.0.1:27017/chatbot")
    .then(() => console.log("✅ MongoDB connected"))
    .catch((err) => {
        console.error("❌ MongoDB connection error:", err);
        process.exit(1);
    });

mongoose.connection.on('connected', () => console.log('✅ Mongoose connected'));
mongoose.connection.on('error', (err) => console.error('❌ Mongoose error:', err));
mongoose.connection.on('disconnected', () => console.log('⚠️ Mongoose disconnected'));

// App Configuration
app.set("view engine", "ejs");
app.set('views', path.join(__dirname, 'views'));

app.use(cors({ origin: '*' })); // Allow all origins for simplicity
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(checkForAuthenticationCookie("token"));

// Routes
app.use('/', userRouter);
app.use('/chat', chatRouter);

app.get('/', (req, res) => res.render('home'));

// Start Server
app.listen(PORT, () => console.log(`🚀 Server running at http://localhost:${PORT}`));