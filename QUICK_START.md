# ⚡ Quick Start Guide

Get LUMEN up and running in 5 minutes!

---

## 🎯 Prerequisites Checklist

```bash
# Check Node.js version (need 18+)
node --version

# Check Python version (need 3.11+)
python --version

# Check Git
git --version
```

---

## 🚀 Installation (5 Minutes)

### Step 1: Clone & Navigate (30 seconds)

```bash
git clone https://github.com/CoderUzumaki/Lumen.git
cd Lumen
```

### Step 2: Frontend Setup (2 minutes)

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:5000
```

```bash
npm run dev
```

✅ Frontend running at http://localhost:3000

### Step 3: Backend Setup (2.5 minutes)

Open new terminal:

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create `backend/.env`:

```bash
OPENROUTER_API_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
DATABASE_URL=sqlite:///instance/lumen.db
```

```bash
python app.py
```

✅ Backend running at http://localhost:5000

---

## 🎮 First Use

### 1. Visit the Landing Page

Open browser → http://localhost:3000

### 2. Navigate to Dashboard

Click "Get Started" or use sidebar

### 3. Upload Your First Invoice

-   Click "Upload Invoice" button
-   Drag & drop an invoice image/PDF
-   Wait for OCR processing (2-3 seconds)
-   View extracted data!

### 4. Try the Chat Interface

-   Go to "Chat Bot" page
-   Ask: "Show me all invoices"
-   Get AI-powered response with data

### 5. Explore Analytics

-   Visit "Analytics" page for basic stats
-   Visit "AI Analytics" for advanced insights
-   See forecasts, anomalies, and patterns

---

## 🔑 Getting API Keys

### OpenRouter (Required for Chat)

1. Go to https://openrouter.ai/
2. Sign up for free account
3. Navigate to "Keys" section
4. Create new API key
5. Copy to `.env` file

**Free tier**: $5 credit for testing

### Google Cloud Vision (Required for OCR)

1. Go to https://console.cloud.google.com/
2. Create new project
3. Enable "Cloud Vision API"
4. Create service account
5. Download JSON key file
6. Save in backend directory
7. Update path in `.env`

**Free tier**: 1000 requests/month

---

## 🧪 Test with Sample Data

### Sample Invoices

We provide sample invoices in `backend/sample_invoices/`:

-   `sample_invoice_1.pdf` - Tech company invoice
-   `sample_invoice_2.jpg` - Office supplies invoice
-   `sample_invoice_3.png` - Cloud services invoice

### Upload Sample Invoice

```bash
# Using cURL
curl -X POST http://localhost:5000/extract \
  -F "file=@backend/sample_invoices/sample_invoice_1.pdf" \
  -F "user_id=demo_user"
```

Or use the web interface!

---

## 🎨 Customize Configuration

### Change Port Numbers

**Frontend** (`frontend/package.json`):

```json
"scripts": {
  "dev": "next dev -p 3001"
}
```

**Backend** (`backend/app.py`):

```python
app.run(debug=True, port=5001)
```

### Change Database

Edit `backend/.env`:

```bash
# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost/lumen

# MySQL
DATABASE_URL=mysql://user:pass@localhost/lumen
```

---

## 🐛 Common Issues & Fixes

### Issue: Port Already in Use

```bash
# Windows - Kill port 3000
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Mac/Linux - Kill port 3000
lsof -ti:3000 | xargs kill -9
```

### Issue: Module Not Found

```bash
# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install

# Backend
pip install -r requirements.txt --force-reinstall
```

### Issue: API Key Not Working

-   Check `.env` file exists in correct directory
-   Verify no extra spaces in API key
-   Ensure no quotes around the key
-   Restart server after changing `.env`

### Issue: Database Error

```bash
# Reset database
rm backend/instance/lumen.db
python backend/app.py  # Will recreate
```

---

## 📚 Next Steps

1. ✅ Read [Full Setup Guide](SETUP.md) for detailed instructions
2. ✅ Check [Architecture](ARCHITECTURE.md) to understand the system
3. ✅ Review [API Documentation](API_DOCS.md) for integration
4. ✅ See [Contributing Guide](CONTRIBUTING.md) to contribute

---

## 🎯 Quick Command Reference

### Start Development

```bash
# Terminal 1 - Frontend
cd frontend && npm run dev

# Terminal 2 - Backend
cd backend && .\venv\Scripts\Activate.ps1 && python app.py
```

### Run Tests

```bash
# Frontend
cd frontend && npm test

# Backend
cd backend && pytest
```

### Build for Production

```bash
# Frontend
cd frontend && npm run build

# Backend
# Use Gunicorn or similar
gunicorn -w 4 app:app
```

---

## 💡 Pro Tips

1. **Use VS Code**: Great for TypeScript/Python development
2. **Install Extensions**:
    - ESLint (JavaScript)
    - Pylance (Python)
    - Prettier (Formatting)
3. **Enable Auto-save**: Never lose changes
4. **Use Git Branches**: One branch per feature
5. **Read Error Messages**: They usually tell you what's wrong!

---

## 🆘 Get Help

-   **Documentation**: Check other .md files in repo
-   **GitHub Issues**: Report bugs or ask questions
-   **Email**: team@dunder-pressure.dev

---

## ✅ Success Checklist

-   [ ] Both servers running without errors
-   [ ] Landing page loads at localhost:3000
-   [ ] Backend health check returns OK
-   [ ] Sample invoice uploads successfully
-   [ ] OCR extraction works
-   [ ] Chat interface responds
-   [ ] Analytics page loads data

---

<div align="center">

**You're ready to go! 🚀**

Start exploring LUMEN and upload your first invoice!

</div>
