# 🚀 Setup Guide

Complete step-by-step guide to set up and run LUMEN on your local machine.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

-   **Node.js** (v18.0.0 or higher) - [Download](https://nodejs.org/)
-   **Python** (v3.11 or higher) - [Download](https://www.python.org/)
-   **Git** - [Download](https://git-scm.com/)
-   **npm** or **yarn** (comes with Node.js)

### API Keys Required

You'll need to obtain the following API keys:

1. **OpenRouter API Key** (for LLM)

    - Sign up at [OpenRouter](https://openrouter.ai/)
    - Navigate to API Keys section
    - Create a new API key

2. **Google Cloud Vision API Key** (for OCR)
    - Create a project at [Google Cloud Console](https://console.cloud.google.com/)
    - Enable Vision API
    - Create service account and download JSON key

---

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/CoderUzumaki/Lumen.git
cd Lumen
```

---

## 🎨 Frontend Setup

### 1. Navigate to Frontend Directory

```bash
cd frontend
```

### 2. Install Dependencies

```bash
npm install
```

**Dependencies include:**

-   Next.js 14.2.5
-   React 18.3.1
-   TypeScript
-   Tailwind CSS
-   Framer Motion
-   Recharts
-   Radix UI components
-   Axios

### 3. Configure Environment Variables

Create a `.env.local` file in the `frontend` directory:

```bash
# .env.local

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:5000

# Application URL
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 4. Run Development Server

```bash
npm run dev
```

The frontend will be available at **http://localhost:3000**

### 5. Build for Production (Optional)

```bash
npm run build
npm start
```

---

## 🔙 Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Virtual Environment

**On Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Key dependencies:**

-   Flask 3.0.0
-   Flask-CORS
-   Flask-SQLAlchemy
-   OpenAI
-   Google Cloud Vision
-   ChromaDB
-   Sentence Transformers
-   Scikit-learn
-   Pandas, NumPy
-   Alembic (migrations)

### 4. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
# .env

# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct

# Google Cloud Vision API
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# Database Configuration
DATABASE_URL=sqlite:///instance/lumen.db
# For PostgreSQL: postgresql://username:password@localhost:5432/lumen

# Flask Configuration
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=your-secret-key-here

# CORS Settings
CORS_ORIGINS=http://localhost:3000

# Application Settings
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB max file size
```

### 5. Set Up Google Cloud Vision

**Option 1: Service Account JSON**

1. Download your service account JSON key from Google Cloud Console
2. Save it in the backend directory (e.g., `google-credentials.json`)
3. Update `GOOGLE_APPLICATION_CREDENTIALS` in `.env`

**Option 2: Environment Variable**

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### 6. Initialize Database

```bash
# Create database tables
python -c "from models.database import init_db; from flask import Flask; app = Flask(__name__); init_db(app)"
```

Or simply run the app once (it will auto-create tables):

```bash
python app.py
```

### 7. Run Development Server

**Using Python directly:**

```bash
python app.py
```

**Using PowerShell script (Windows):**

```powershell
.\start.ps1
```

The backend will be available at **http://localhost:5000**

### 8. Verify Backend is Running

Visit **http://localhost:5000/health** - you should see:

```json
{
	"status": "healthy",
	"timestamp": "2025-11-15T10:30:00Z"
}
```

---

## 🗄️ Database Setup

### SQLite (Default - Development)

-   No additional setup required
-   Database file created automatically at `backend/instance/lumen.db`
-   Good for development and testing

### PostgreSQL (Production)

1. **Install PostgreSQL**

    - Download from [postgresql.org](https://www.postgresql.org/download/)
    - Create a new database: `createdb lumen`

2. **Update .env**

    ```bash
    DATABASE_URL=postgresql://username:password@localhost:5432/lumen
    ```

3. **Run Migrations**
    ```bash
    alembic upgrade head
    ```

---

## 🧪 Testing the Application

### 1. Test OCR Extraction

```bash
# Using curl
curl -X POST http://localhost:5000/extract \
  -F "file=@path/to/invoice.jpg" \
  -F "user_id=test_user"
```

### 2. Test Chat Interface

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all invoices",
    "user_id": "test_user"
  }'
```

### 3. Test Analytics

```bash
curl http://localhost:5000/analytics/summary?user_id=test_user
```

---

## 📁 Project Structure

```
Lumen/
├── frontend/                 # Next.js frontend
│   ├── src/
│   │   ├── app/             # App router pages
│   │   │   ├── page.tsx     # Landing page
│   │   │   ├── dashboard/   # Dashboard page
│   │   │   ├── analytics/   # Analytics page
│   │   │   ├── ai-analytics/# AI Analytics page
│   │   │   └── chatbot/     # Chat interface
│   │   ├── components/      # React components
│   │   │   ├── landing/     # Landing page components
│   │   │   ├── analytics/   # Analytics components
│   │   │   ├── ai-analytics/# AI Analytics components
│   │   │   ├── chatbot/     # Chat components
│   │   │   └── ui/          # Shadcn UI components
│   │   ├── lib/             # Utilities and helpers
│   │   └── styles/          # Global styles
│   ├── public/              # Static assets
│   ├── package.json         # Dependencies
│   └── next.config.js       # Next.js config
│
├── backend/                 # Flask backend
│   ├── app.py              # Main application entry
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Python dependencies
│   ├── routes/             # API routes
│   │   ├── analytics.py    # Analytics endpoints
│   │   ├── chat.py         # Chat endpoints
│   │   ├── database_query.py # Query endpoints
│   │   ├── ocr.py          # OCR endpoints
│   │   ├── batch.py        # Batch processing
│   │   └── health.py       # Health check
│   ├── ai/                 # AI agents and systems
│   │   ├── hybrid_query_engine.py  # Main query orchestrator
│   │   ├── query_classifier.py     # Query type classifier
│   │   ├── sql_agent.py            # SQL query generator
│   │   ├── rag_system.py           # RAG for documents
│   │   ├── analytics_orchestrator.py # Analytics coordinator
│   │   ├── pattern_detection.py    # Pattern analysis
│   │   ├── anomaly_detection.py    # Fraud detection
│   │   ├── forecasting_agent.py    # Spending forecasts
│   │   └── risk_assessment.py      # Risk analysis
│   ├── models/             # Database models
│   │   └── database.py     # SQLAlchemy models
│   ├── utils/              # Utility functions
│   │   ├── openrouter.py   # LLM integration
│   │   ├── image_processing.py # OCR processing
│   │   ├── analytics_service.py # Analytics helpers
│   │   └── normalize.py    # Data normalization
│   ├── instance/           # Database files
│   ├── chroma_db/          # Vector database
│   └── uploads/            # Uploaded files
│
├── docs/                   # Documentation
│   └── screenshots/        # Application screenshots
│
├── README.md              # Main documentation
├── SETUP.md               # This file
├── ARCHITECTURE.md        # Architecture details
├── PROBLEM_STATEMENT.md   # Original problem statement
└── .gitignore            # Git ignore rules
```

---

## 🐛 Troubleshooting

### Frontend Issues

**Issue: Port 3000 already in use**

```bash
# Kill the process using port 3000
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:3000 | xargs kill -9
```

**Issue: Module not found errors**

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**Issue: Next.js cache issues**

```bash
# Clear Next.js cache
rm -rf .next
npm run dev
```

### Backend Issues

**Issue: Port 5000 already in use**

```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

**Issue: ModuleNotFoundError**

```bash
# Ensure virtual environment is activated
# Reinstall dependencies
pip install -r requirements.txt
```

**Issue: Google Vision API authentication failed**

-   Verify service account JSON is valid
-   Check `GOOGLE_APPLICATION_CREDENTIALS` path
-   Ensure Vision API is enabled in Google Cloud Console
-   Verify billing is enabled on Google Cloud project

**Issue: Database errors**

```bash
# Delete and recreate database
rm -rf instance/lumen.db
python app.py
```

**Issue: ChromaDB errors**

```bash
# Clear ChromaDB
rm -rf chroma_db/
python app.py  # Will reinitialize
```

### Common Issues

**Issue: CORS errors**

-   Ensure backend `.env` has correct `CORS_ORIGINS`
-   Verify frontend is running on expected port
-   Check Flask-CORS is installed

**Issue: API key not working**

-   Verify API keys are correctly set in `.env`
-   Check for extra spaces or quotes
-   Ensure `.env` file is in the correct directory
-   Restart backend server after changing `.env`

---

## 🔒 Security Notes

### API Keys

-   **Never commit API keys to Git**
-   Use `.env` files (already in `.gitignore`)
-   Rotate keys if accidentally exposed
-   Use environment-specific keys

### Production Deployment

-   Use PostgreSQL instead of SQLite
-   Enable HTTPS
-   Set strong `SECRET_KEY`
-   Configure proper CORS origins
-   Enable rate limiting
-   Use environment variables for all secrets
-   Regular security audits

---

## 📊 Performance Optimization

### Frontend

-   Enable Next.js image optimization
-   Use dynamic imports for heavy components
-   Implement code splitting
-   Enable React Strict Mode
-   Use production build for deployment

### Backend

-   Use connection pooling for database
-   Enable caching for frequent queries
-   Optimize SQL queries with indexes
-   Use background tasks for heavy processing
-   Implement request rate limiting

---

## 🚢 Deployment

### Frontend (Vercel)

1. Push code to GitHub
2. Connect repository to Vercel
3. Configure environment variables
4. Deploy automatically on push

### Backend (Render/Railway)

1. Push code to GitHub
2. Connect repository to hosting platform
3. Configure environment variables
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python app.py`

---

## 📚 Additional Resources

-   [Next.js Documentation](https://nextjs.org/docs)
-   [Flask Documentation](https://flask.palletsprojects.com/)
-   [OpenRouter API Docs](https://openrouter.ai/docs)
-   [Google Cloud Vision API](https://cloud.google.com/vision/docs)
-   [ChromaDB Documentation](https://docs.trychroma.com/)

---

## 💬 Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review error messages carefully
3. Check GitHub Issues
4. Contact the team

---

## ✅ Verification Checklist

-   [ ] Node.js and Python installed
-   [ ] Repository cloned
-   [ ] Frontend dependencies installed
-   [ ] Backend virtual environment created
-   [ ] Backend dependencies installed
-   [ ] Environment variables configured
-   [ ] API keys obtained and set
-   [ ] Database initialized
-   [ ] Frontend running on port 3000
-   [ ] Backend running on port 5000
-   [ ] Health endpoint accessible
-   [ ] Test invoice processed successfully

---

<div align="center">

**You're all set! 🎉**

Start by visiting **http://localhost:3000** and upload your first invoice!

</div>
