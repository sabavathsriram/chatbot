const jwt = require('jsonwebtoken');

const JWT_SECRET = 'hacunamatata';

function checkForAuthenticationCookie(cookieName) {
    return (req, res, next) => {
        console.log('Cookies:', req.cookies);
        const token = req.cookies[cookieName];
        console.log('Token:', token);
        if (!token) {
            req.user = null;
            return next();
        }
        try {
            const payload = jwt.verify(token, JWT_SECRET);
            console.log('Verified payload:', payload);
            req.user = payload;
            next();
        } catch (e) {
            console.error('JWT verification error:', e.message);
            req.user = null;
            next();
        }
    };
}

module.exports = { checkForAuthenticationCookie };