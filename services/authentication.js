const jwt = require('jsonwebtoken');

const JWT_SECRET = 'hacunamatata';

function createTokenForUser(user) {
    const payload = {
        id: user._id,
        username: user.username,
        email: user.email
    };
    return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' });
}

module.exports = { createTokenForUser };