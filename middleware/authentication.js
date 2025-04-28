const jwt = require('jsonwebtoken');

     function checkForAuthenticationCookie(cookieName) {
         return (req, res, next) => {
             const token = req.cookies[cookieName];
             if (!token) {
                 req.user = null;
                 return next();
             }
             try {
                 const payload = jwt.verify(token, 'your_jwt_secret'); // Replace with your JWT secret
                 req.user = payload;
                 next();
             } catch (e) {
                 req.user = null;
                 next();
             }
         };
     }

     module.exports = { checkForAuthenticationCookie };