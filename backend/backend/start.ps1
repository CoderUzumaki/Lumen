# Lumen Backend Startup Script

Write-Host "Starting Lumen Backend..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "Warning: .env file not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Please edit .env file with your Supabase credentials" -ForegroundColor Yellow
    exit 1
}

# Start Flask application
Write-Host "Starting Flask server on http://localhost:5000" -ForegroundColor Cyan
python app.py
