# 🚢 Deployment Guide

Complete guide for deploying LUMEN to production environments.

---

## 📋 Pre-Deployment Checklist

-   [ ] All tests passing
-   [ ] Environment variables configured
-   [ ] API keys secured
-   [ ] Database migrations ready
-   [ ] Build process tested locally
-   [ ] Security audit completed
-   [ ] Performance optimization done
-   [ ] Monitoring setup planned

---

## 🎨 Frontend Deployment (Vercel)

### Why Vercel?

-   Built for Next.js
-   Automatic deployments
-   Global CDN
-   Zero configuration
-   Free tier available

### Step 1: Prepare for Deployment

```bash
cd frontend

# Test production build locally
npm run build
npm start

# Verify everything works
```

### Step 2: Deploy to Vercel

#### Option A: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
cd frontend
vercel

# Follow prompts
# Set root directory: frontend
# Override settings: No
```

#### Option B: GitHub Integration

1. Push code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "New Project"
4. Import your repository
5. Configure:
    - **Framework**: Next.js
    - **Root Directory**: `frontend`
    - **Build Command**: `npm run build`
    - **Output Directory**: `.next`

### Step 3: Configure Environment Variables

In Vercel dashboard:

```bash
NEXT_PUBLIC_API_URL=https://your-backend-api.com
NEXT_PUBLIC_APP_URL=https://your-app.vercel.app
```

### Step 4: Custom Domain (Optional)

1. Go to Project Settings → Domains
2. Add your domain
3. Configure DNS records as instructed
4. Wait for SSL certificate (automatic)

---

## 🔙 Backend Deployment (Render)

### Why Render?

-   Easy Python deployment
-   PostgreSQL included
-   Environment variables
-   Automatic deploys
-   Free tier available

### Step 1: Prepare Backend

#### Update `requirements.txt`

Add production dependencies:

```txt
gunicorn==21.2.0
psycopg2-binary==2.9.9
```

#### Create `render.yaml`

```yaml
services:
    - type: web
      name: lumen-backend
      env: python
      buildCommand: pip install -r requirements.txt
      startCommand: gunicorn app:app
      envVars:
          - key: PYTHON_VERSION
            value: 3.11.0
          - key: FLASK_ENV
            value: production
```

### Step 2: Deploy to Render

1. Go to [render.com](https://render.com)
2. Sign in with GitHub
3. Click "New +" → "Web Service"
4. Connect repository
5. Configure:
    - **Name**: lumen-backend
    - **Environment**: Python 3
    - **Build Command**: `pip install -r requirements.txt`
    - **Start Command**: `gunicorn app:app -b 0.0.0.0:$PORT`
    - **Root Directory**: `backend`

### Step 3: Add PostgreSQL Database

1. In Render dashboard, click "New +" → "PostgreSQL"
2. Create database
3. Copy database URL
4. Add to web service environment variables

### Step 4: Environment Variables

Add in Render dashboard:

```bash
DATABASE_URL=<from PostgreSQL service>
OPENROUTER_API_KEY=sk-xxxxx
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/google-creds.json
SECRET_KEY=<generate-strong-key>
FLASK_ENV=production
CORS_ORIGINS=https://your-app.vercel.app
```

### Step 5: Add Google Credentials

1. Convert JSON to base64:
    ```bash
    cat google-creds.json | base64
    ```
2. Add as secret file in Render
3. Path: `/etc/secrets/google-creds.json`

---

## 🗄️ Database Migration

### From SQLite to PostgreSQL

```bash
# Export data from SQLite
python scripts/export_data.py

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:pass@host:5432/lumen

# Run migrations
alembic upgrade head

# Import data
python scripts/import_data.py
```

### Run Migrations on Render

Render automatically runs migrations if you add:

```bash
# In render.yaml
services:
  - type: web
    preDeployCommand: alembic upgrade head
```

---

## 🔒 Security Configuration

### 1. HTTPS Only

Frontend automatically uses HTTPS on Vercel.

For backend, Render provides free SSL.

### 2. CORS Configuration

```python
# backend/app.py
CORS(app,
     origins=[
         'https://your-app.vercel.app',
         'https://www.your-domain.com'
     ],
     supports_credentials=True)
```

### 3. API Key Rotation

-   Use Render secrets for sensitive data
-   Rotate keys monthly
-   Never commit keys to Git

### 4. Rate Limiting

```python
# backend/app.py
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

---

## 📊 Monitoring Setup

### Frontend Monitoring (Vercel Analytics)

1. Enable in Vercel dashboard
2. Add to `app/layout.tsx`:

```typescript
import { Analytics } from "@vercel/analytics/react";

export default function RootLayout({ children }) {
	return (
		<html>
			<body>
				{children}
				<Analytics />
			</body>
		</html>
	);
}
```

### Backend Monitoring (Sentry)

```bash
# Install Sentry
pip install sentry-sdk[flask]
```

```python
# backend/app.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0
)
```

### Logging

```python
# backend/app.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
    push:
        branches: [main]

jobs:
    test:
        runs-on: ubuntu-latest
        steps:
            - uses: actions/checkout@v3

            - name: Setup Node
              uses: actions/setup-node@v3
              with:
                  node-version: "18"

            - name: Install & Test Frontend
              run: |
                  cd frontend
                  npm install
                  npm run build
                  npm test

            - name: Setup Python
              uses: actions/setup-python@v4
              with:
                  python-version: "3.11"

            - name: Install & Test Backend
              run: |
                  cd backend
                  pip install -r requirements.txt
                  pytest

    deploy:
        needs: test
        runs-on: ubuntu-latest
        steps:
            - name: Deploy to Vercel
              uses: amondnet/vercel-action@v20
              with:
                  vercel-token: ${{ secrets.VERCEL_TOKEN }}
                  vercel-org-id: ${{ secrets.ORG_ID }}
                  vercel-project-id: ${{ secrets.PROJECT_ID }}
```

---

## 🎯 Performance Optimization

### Frontend

1. **Enable Next.js Image Optimization**

    ```typescript
    import Image from "next/image";

    <Image src="/logo.png" width={100} height={100} alt="Logo" />;
    ```

2. **Code Splitting**

    ```typescript
    const HeavyComponent = dynamic(() => import("./HeavyComponent"));
    ```

3. **Enable Compression**
    ```javascript
    // next.config.js
    module.exports = {
    	compress: true,
    };
    ```

### Backend

1. **Database Connection Pooling**

    ```python
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20
    ```

2. **Response Caching**

    ```python
    from flask_caching import Cache

    cache = Cache(app, config={'CACHE_TYPE': 'redis'})

    @app.route('/analytics')
    @cache.cached(timeout=300)
    def analytics():
        return get_analytics()
    ```

3. **Use Gunicorn Workers**
    ```bash
    gunicorn -w 4 -k gevent app:app
    ```

---

## 🧪 Production Testing

### Load Testing

```bash
# Install Apache Bench
apt-get install apache2-utils

# Test OCR endpoint
ab -n 100 -c 10 -p invoice.pdf \
   https://api.lumen.example.com/extract

# Test analytics
ab -n 1000 -c 50 \
   https://api.lumen.example.com/analytics/summary?user_id=test
```

### Smoke Tests

```bash
# Test health endpoint
curl https://api.lumen.example.com/health

# Test frontend
curl -I https://lumen.vercel.app

# Test CORS
curl -H "Origin: https://lumen.vercel.app" \
     -I https://api.lumen.example.com/health
```

---

## 🔧 Troubleshooting Production Issues

### Frontend Not Loading

1. Check Vercel deployment logs
2. Verify environment variables
3. Check browser console for errors
4. Verify API URL is correct

### Backend Errors

1. Check Render logs: `render logs --tail`
2. Verify database connection
3. Check API keys are set
4. Review Sentry error reports

### Database Issues

1. Check connection string
2. Verify migrations ran
3. Check database size limits
4. Review slow query logs

---

## 📈 Scaling Strategies

### When to Scale

-   Response time > 3 seconds
-   Error rate > 1%
-   CPU usage > 80%
-   Memory usage > 85%

### Horizontal Scaling

1. **Add more backend instances**

    - Render: Increase instance count
    - Use load balancer

2. **Database read replicas**

    - Configure PostgreSQL replication
    - Route read queries to replicas

3. **CDN for static assets**
    - Already handled by Vercel
    - Consider CloudFlare for backend

### Vertical Scaling

1. **Upgrade instance size**

    - More CPU/RAM on Render
    - Better database plan

2. **Optimize queries**
    - Add database indexes
    - Use query optimization

---

## 💰 Cost Estimation

### Free Tier Limits

**Vercel (Frontend)**

-   100 GB bandwidth/month
-   Unlimited requests
-   SSL included
-   **Cost**: $0

**Render (Backend)**

-   750 hours/month
-   512 MB RAM
-   PostgreSQL: 1 GB storage
-   **Cost**: $0

**APIs**

-   OpenRouter: $5 free credit
-   Google Vision: 1000 requests/month
-   **Cost**: ~$0

### Paid Tier (Production)

**Vercel Pro**: $20/month
**Render Starter**: $7/month
**PostgreSQL**: $7/month
**APIs**: ~$50/month

**Total**: ~$84/month for production

---

## 📞 Support

### Production Issues

-   **Vercel**: support@vercel.com
-   **Render**: support@render.com
-   **Our Team**: team@dunder-pressure.dev

---

## ✅ Post-Deployment Checklist

-   [ ] Frontend accessible via HTTPS
-   [ ] Backend health check passing
-   [ ] Database migrations completed
-   [ ] All environment variables set
-   [ ] Monitoring enabled
-   [ ] Logs accessible
-   [ ] Backups configured
-   [ ] Domain configured (if custom)
-   [ ] SSL certificates valid
-   [ ] CORS configured correctly
-   [ ] Rate limiting enabled
-   [ ] Error tracking working
-   [ ] Performance metrics baseline recorded

---

<div align="center">

**Your app is now live! 🎉**

Monitor closely for the first 24 hours and be ready to address any issues.

</div>
