const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) {
    console.error('❌ JWT_SECRET not found in environment variables');
    process.exit(1);
}

function createTokenForUser(user) {
    const payload = {
        id: user._id,
        username: user.username,
        email: user.email
    };
    return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' });
}

module.exports = { createTokenForUser };