const express = require('express');
const router = express.Router();
const User = require('../model/userschema');
const { createTokenForUser } = require('../services/authentication');

// Render Signin Page
router.get('/signin', (req, res) => {
    return res.render('signin');
});

// Render Signup Page
router.get('/signup', (req, res) => {
    return res.render('signup');
});

// Signup Route (Ensure Unique Username & Email)
router.post('/signup', async (req, res) => {
    const { username, email, password } = req.body;

    try {
        // Check if Username OR Email already exists
        const existingUser = await User.findOne({
            $or: [{ email }, { username }]
        });

        if (existingUser) {
            return res.render('signup', { error: 'Username or Email already exists' });
        }

        // Create New User
        await User.create({ username, email, password });

        return res.redirect('/signin'); // Redirect to signin page after signup
    } catch (error) {
        return res.render('signup', { error: 'Signup failed, try again' });
    }
});

// Signin Route (Allow Login via Username or Email)
router.post('/signin', async (req, res) => {
    try {
        const { login, password } = req.body;

        // Find User by Either Username OR Email
        const user = await User.matchPasswordAndGenerateToken(login, password);

        if (!user) {
            return res.render('signin', { error: 'Incorrect Username/Email or Password' });
        }

        // Generate Token and Set Cookie
        const token = createTokenForUser(user);
        return res.cookie('token', token).redirect('/');
    } catch (error) {
        return res.render('signin', { error: 'Incorrect Username/Email or Password' });
    }
});

// Logout Route
router.get('/logout', (req, res) => {
    res.clearCookie("token").redirect('/');
});

module.exports = router;
