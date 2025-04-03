const { createHmac, randomBytes } = require('crypto');
const { Schema, model } = require('mongoose');

const userSchema = new Schema({
    username: {
        type: String,
        required: true,
        unique: true, // Ensures no duplicate usernames
    },
    email: {
        type: String,
        required: true,
        unique: true, // Ensures no duplicate emails
    },
    salt: {
        type: String,
    },
    password: {
        type: String,
        required: true,
    },
}, { timestamps: true });

// Hash password before saving user
userSchema.pre("save", function (next) {
    const user = this;
    if (!user.isModified("password")) return next();

    const salt = randomBytes(16).toString("hex");
    const hashedPassword = createHmac('sha256', salt)
        .update(user.password)
        .digest("hex");

    user.salt = salt;
    user.password = hashedPassword;

    next();
});

// Static method for authentication
userSchema.static("matchPasswordAndGenerateToken", async function (login, password) {
    const user = await this.findOne({ 
        $or: [{ email: login }, { username: login }] 
    });

    if (!user) throw new Error('User not found!');

    const { salt, password: hashedPassword } = user;
    const userProvidedHash = createHmac("sha256", salt)
        .update(password)
        .digest("hex");

    if (hashedPassword !== userProvidedHash) throw new Error("Incorrect Password");

    return user;
});

const User = model('User', userSchema);

module.exports = User;
