const jwt = require('jsonwebtoken');

     function createTokenForUser(user) {
         const payload = {
             _id: user._id,
             username: user.username,
             email: user.email
         };
         return jwt.sign(payload, 'your_jwt_secret', { expiresIn: '1h' }); // Replace with your JWT secret
     }

     module.exports = { createTokenForUser };