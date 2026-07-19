const express = require("express");
const cors = require("cors");
const path = require("path");
const connectDB = require("./src/config/db");
require("dotenv").config();
const jwt = require("jsonwebtoken");

const userRoutes = require("./src/routes/userRoutes");
const therapistRoutes = require("./src/routes/therapistRoutes");
const googleAuthRoutes = require("./routes/googleAuthRoutes");
const conversationRoutes = require("./src/routes/conversationRoutes");
const taskRoutes = require("./src/routes/taskRoutes");
const memoryRoutes = require("./src/routes/memoryRoutes");
const journalRoutes = require("./src/routes/journalRoutes");
const sessionStateRoutes = require("./src/routes/sessionStateRoutes");
const userProfileRoutes = require("./src/routes/userProfileRoutes");

// Connect to database
connectDB();

const app = express();

// CORS configuration - more permissive for development
app.use(
    cors({
        origin: "*", // Allow all origins
        methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allowedHeaders: ["Content-Type", "Authorization", "X-Requested-With"],
        credentials: true,
    }),
);

// Middleware
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// Create uploads directory if it doesn't exist
const fs = require("fs");
const uploadsDir = path.join(__dirname, "uploads");
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
}

// Static folder for uploads
app.use("/uploads", express.static(uploadsDir));

// Minimal request logger (method + url only)
app.use((req, res, next) => {
    console.log(
        `${new Date().toISOString()} - ${req.method} ${req.originalUrl}`,
    );
    next();
});

// Debug routes (only for development)
if (process.env.NODE_ENV === "development") {
    app.get("/debug/jwt", (req, res) => {
        const testPayload = { id: "123456", userType: "user" };
        const token = jwt.sign(testPayload, process.env.JWT_SECRET, {
            expiresIn: "30d",
        });

        try {
            const decoded = jwt.verify(token, process.env.JWT_SECRET);

            res.json({
                message: "JWT DEBUG INFO",
                token,
                decoded,
                secret: process.env.JWT_SECRET.substring(0, 3) + "...",
                success: true,
            });
        } catch (error) {
            res.status(400).json({
                message: "JWT validation failed",
                error: error.message,
                secret: process.env.JWT_SECRET.substring(0, 3) + "...",
                success: false,
            });
        }
    });
}

// Routes
app.use("/api/users", userRoutes);
app.use("/api/therapists", therapistRoutes);
app.use("/api/auth/google", googleAuthRoutes);
app.use("/api/conversations", conversationRoutes);
app.use("/api/tasks", taskRoutes);
app.use("/api/memories", memoryRoutes);
app.use("/api/journals", journalRoutes);
app.use("/api/session-state", sessionStateRoutes);
app.use("/api/user-profile", userProfileRoutes);

// Options for preflight requests
app.options("*", cors());

// Home route
app.get("/", (req, res) => {
    res.send("API is running...");
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error(`Error: ${err.message}`);
    console.error(err.stack);

    res.status(err.statusCode || 500).json({
        message: err.message || "Server Error",
        stack: process.env.NODE_ENV === "production" ? null : err.stack,
    });
});

// Handle 404 errors
app.use((req, res) => {
    res.status(404).json({ message: `Route ${req.originalUrl} not found` });
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(
        `Server running in ${process.env.NODE_ENV} mode on port ${PORT}`,
    );
    console.log(`CORS is enabled for all origins in development mode`);
});
