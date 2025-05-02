const mongoose = require('mongoose');
const bcrypt = require('bcrypt');

const userSchema = new mongoose.Schema({
    username: {
        type: String,
        required: true,
        unique: true,
        trim: true
    },
    email: {
        type: String,
        required: true,
        unique: true,
        trim: true
    },
    password: {
        type: String,
        required: true
    }
});

// Hash password before saving
userSchema.pre('save', async function (next) {
    if (this.isModified('password')) {
        console.log('Hashing password for user:', this.username);
        this.password = await bcrypt.hash(this.password, 10);
    }
    next();
});

// Method to match password and return user
userSchema.statics.matchPasswordAndGenerateToken = async function (login, password) {
    console.log('Querying user with login:', login);
    const user = await this.findOne({
        $or: [{ email: login }, { username: login }]
    });
    if (!user) {
        console.log('User not found for login:', login);
        return null;
    }
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
        console.log('Password mismatch for login:', login);
        return null;
    }
    console.log('User authenticated:', user.username);
    return user;
};

module.exports = mongoose.model('User', userSchema);