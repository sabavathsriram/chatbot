const jwt = require('jsonwebtoken');

const createTokenForUser = (user) => {
    return jwt.sign(
        { id: user._id, email: user.email, username: user.username },
        "your_secret_key",
        { expiresIn: "1h" }
    );
};

module.exports = { createTokenForUser };
