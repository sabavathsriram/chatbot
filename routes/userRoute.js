const express = require('express');
const router = express.Router();
const User = require('../model/userschema');
const { createTokenForUser } = require('../services/authentication');

// Render Signin Page
router.get('/signin', (req, res) => {
    return res.render('signin', { error: null });
});

// Render Signup Page
router.get('/signup', (req, res) => {
    return res.render('signup', { error: null });
});

// Signup Route (Ensure Unique Username & Email)
router.post('/signup', async (req, res) => {
    const { username, email, password } = req.body;

    // Input validation
    if (!username || !email || !password) {
        return res.render('signup', { error: 'All fields (username, email, password) are required' });
    }

    try {
        // Check MongoDB connection state
        if (require('mongoose').connection.readyState !== 1) {
            throw new Error('Database connection is not established');
        }

        // Check if Username OR Email already exists
        const existingUser = await User.findOne({
            $or: [{ email }, { username }]
        });

        if (existingUser) {
            return res.render('signup', { error: 'Username or Email already exists' });
        }

        // Create New User
        await User.create({ username, email, password });

        return res.redirect('/signin');
    } catch (error) {
        console.error('Signup error:', error.message);
        return res.render('signup', { error: 'Signup failed: ' + error.message });
    }
});

// Signin Route (Allow Login via Username or Email)
router.post('/signin', async (req, res) => {
    const { login, password } = req.body;

    // Input validation
    if (!login || !password) {
        return res.render('signin', { error: 'Username/Email and password are required' });
    }

    try {
        // Check MongoDB connection state
        if (require('mongoose').connection.readyState !== 1) {
            throw new Error('Database connection is not established');
        }

        // Find User by Either Username OR Email
        const user = await User.matchPasswordAndGenerateToken(login, password);

        if (!user) {
            console.log('Signin failed: Incorrect Username/Email or Password for login:', login);
            return res.render('signin', { error: 'Incorrect Username/Email or Password' });
        }

        // Generate Token and Set Cookie
        const token = createTokenForUser(user);
        console.log('Token generated:', token); // Debug log
        return res
            .cookie('token', token, {
                httpOnly: true,
                secure: false, // Set to true in production with HTTPS
                sameSite: 'strict',
                maxAge: 3600000
            })
            .redirect('/');
    } catch (error) {
        console.error('Signin error:', error.message);
        return res.render('signin', { error: 'Signin failed: ' + error.message });
    }
});

router.get('/', (req, res) => {
    res.render('home');
  });

// Logout Route
router.get('/logout', (req, res) => {
    res.clearCookie('token').redirect('/');
});

module.exports = router;