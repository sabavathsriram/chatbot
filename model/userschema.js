const mongoose = require('mongoose');
     const bcrypt = require('bcrypt');
     const jwt = require('jsonwebtoken');

     const userSchema = new mongoose.Schema({
         username: { type: String, required: true, unique: true },
         email: { type: String, required: true, unique: true },
         password: { type: String, required: true }
     });

     // Hash password before saving
     userSchema.pre('save', async function (next) {
         if (!this.isModified('password')) return next();
         this.password = await bcrypt.hash(this.password, 10);
         next();
     });

     // Match password and generate token
     userSchema.statics.matchPasswordAndGenerateToken = async function (login, password) {
         const user = await this.findOne({
             $or: [{ email: login }, { username: login }]
         });
         if (!user) return null;
         const isMatch = await bcrypt.compare(password, user.password);
         if (!isMatch) return null;
         return user;
     };

     module.exports = mongoose.model('User', userSchema);