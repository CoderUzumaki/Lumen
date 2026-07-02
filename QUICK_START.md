# ⚡ Quick Start Guide

Get Lumen up and running in 5 minutes.

---

## Prerequisites

- Node.js 18+
- Python 3.11+
- [OpenRouter API key](https://openrouter.ai/)
- [Supabase project](https://supabase.com/) with Google OAuth enabled

---

## 1. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
```

Set in `frontend/.env.local`:

```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:5000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

```bash
npm run dev
```

Open http://localhost:3000

---

## 2. Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
# source venv/bin/activate    # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
```

Set in `backend/.env`:

```bash
SECRET_KEY=generate-a-long-random-string
OPENROUTER_API_KEY=your_key
SUPABASE_URL=https://your-project.supabase.co
LLM_TEXT_MODEL=openrouter/free

# Optional: Neon/Postgres (omit to use local SQLite)
# DATABASE_URL=postgresql://...
```

**Local SQLite (default):** omit `DATABASE_URL` — data lives in `backend/instance/lumen.db`.

**Neon/Postgres:** set `DATABASE_URL`, then:

```bash
alembic upgrade head
```

```bash
python app.py
```

API at http://localhost:5000

---

## 3. Supabase Google OAuth

In Supabase → Authentication → Providers → Google:

- Add Google Client ID + Secret
- Google Cloud redirect URI: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`

In Supabase → URL Configuration:

- Site URL: `http://localhost:3000`
- Redirect URLs: `http://localhost:3000/signin`

---

## 4. Seed demo data (optional)

```bash
cd backend
python scripts/populate_db.py --user-id YOUR_SUPABASE_USER_UUID
```

Or migrate legacy `user_id='123'` rows:

```bash
python scripts/migrate_demo_user_id.py
```

---

## 5. Sign in and test

1. Open http://localhost:3000/signin
2. Sign in with Google
3. Upload an invoice on the dashboard
4. Try Chat, Analytics, and AI Analytics

---

## Deploy (Render)

See `render.yaml` and `DEPLOYMENT.md`. Use managed Postgres (`DATABASE_URL`), set `ENABLE_CHROMA=false` on the API service, and run the `lumen-email-worker` for IMAP polling.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `auth_misconfigured` | Set `SUPABASE_URL` in backend `.env` and restart |
| `NEXT_PUBLIC_SUPABASE_URL is not set` | Restart `npm run dev` after editing `.env.local` |
| `No module named 'psycopg2'` | `pip install psycopg2-binary` when using `DATABASE_URL` |
| Empty dashboard after login | Seed data with your Supabase UUID or upload invoices |
| Gmail OAuth button fails | Use IMAP + app password instead (OAuth not implemented) |
