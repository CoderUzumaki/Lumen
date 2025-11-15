# 🏗️ Architecture Documentation

Comprehensive technical architecture of the LUMEN invoice management system.

---

## 📐 System Overview

LUMEN follows a modern **microservices-inspired architecture** with clear separation between frontend, backend, and AI services.

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Browser    │  │    Mobile    │  │   Tablet     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│                  (Next.js 14 Frontend)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Landing  │  │Dashboard │  │Analytics │  │ Chatbot  │   │
│  │  Page    │  │   Page   │  │   Page   │  │  Page    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │  REST API   │
                    └──────┬──────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│                    (Flask Backend)                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │   OCR   │  │  Chat   │  │Analytics│  │Database │       │
│  │ Routes  │  │ Routes  │  │ Routes  │  │ Routes  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼              ▼
┌──────────────────────┐  ┌──────────────────────┐
│    AI/ML LAYER       │  │    DATA LAYER        │
│  ┌──────────────┐    │  │  ┌──────────────┐   │
│  │   Hybrid     │    │  │  │  PostgreSQL  │   │
│  │Query Engine  │    │  │  │  /SQLite     │   │
│  └──────────────┘    │  │  └──────────────┘   │
│  ┌──────────────┐    │  │  ┌──────────────┐   │
│  │ Analytics    │    │  │  │   ChromaDB   │   │
│  │ Orchestrator │    │  │  │   (Vector)   │   │
│  └──────────────┘    │  │  └──────────────┘   │
└──────────────────────┘  └──────────────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌─────────┐  ┌─────────────┐
│ Google  │  │ OpenRouter  │
│ Vision  │  │  LLM API    │
│   API   │  │             │
└─────────┘  └─────────────┘
```

---

## 🎨 Frontend Architecture

### Technology Stack

-   **Framework**: Next.js 14.2.5 (App Router)
-   **Language**: TypeScript 5.5.4
-   **Styling**: Tailwind CSS 4.1.17
-   **UI Library**: Radix UI + Shadcn/ui
-   **State Management**: React Hooks (useState, useEffect)
-   **HTTP Client**: Axios 1.7.2
-   **Animations**: Framer Motion 12.23.24
-   **Charts**: Recharts 3.4.1

### Directory Structure

```
frontend/src/
├── app/                      # Next.js App Router
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Landing page
│   ├── globals.css          # Global styles
│   ├── dashboard/           # Dashboard route
│   ├── analytics/           # Analytics route
│   ├── ai-analytics/        # AI Analytics route
│   └── chatbot/             # Chatbot route
│
├── components/
│   ├── landing/             # Landing page components
│   │   ├── hero-section.tsx
│   │   ├── features-section.tsx
│   │   ├── testimonials-section.tsx
│   │   └── ...
│   ├── analytics/           # Analytics components
│   │   ├── analyticsCards.tsx
│   │   └── spendingTrendChart.tsx
│   ├── ai-analytics/        # AI Analytics components
│   │   ├── quickStatsCard.tsx
│   │   ├── anomalyDetectionCard.tsx
│   │   ├── spendingTrendGraph.tsx
│   │   └── ...
│   ├── chatbot/             # Chat interface components
│   │   ├── ChatPane.tsx
│   │   ├── Composer.tsx
│   │   └── ConversationRow.tsx
│   └── ui/                  # Reusable UI components
│       ├── button.tsx
│       ├── card.tsx
│       └── ...
│
├── lib/
│   ├── api/                 # API client functions
│   └── utils.ts             # Utility functions
│
└── hooks/
    ├── use-mobile.ts        # Mobile detection hook
    └── use-toast.ts         # Toast notifications hook
```

### Key Features

#### 1. Server-Side Rendering (SSR)

-   Landing page: Static generation for SEO
-   Dashboard/Analytics: Client-side rendering for interactivity
-   Chatbot: Hybrid rendering

#### 2. Component Architecture

```typescript
// Example: AI Analytics Card Component
"use client";

interface CardProps {
	title: string;
	data: any;
	loading?: boolean;
}

export function AnalyticsCard({ title, data, loading }: CardProps) {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5 }}
		>
			<Card className="bg-slate-900/50 border-slate-800">
				{/* Card content */}
			</Card>
		</motion.div>
	);
}
```

#### 3. API Integration

```typescript
// lib/api/analytics.ts
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getQuickStats(userId: string) {
	const response = await axios.get(
		`${API_URL}/analytics/quick-stats?user_id=${userId}`
	);
	return response.data;
}
```

#### 4. Responsive Design

-   Mobile-first approach
-   Breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
-   Tailwind utility classes for responsive layouts

---

## 🔙 Backend Architecture

### Technology Stack

-   **Framework**: Flask 3.0.0
-   **Language**: Python 3.11+
-   **Database ORM**: SQLAlchemy 2.0+
-   **Migrations**: Alembic 1.17.1
-   **CORS**: Flask-CORS 4.0.0
-   **AI/ML**: Custom agents + external APIs

### Directory Structure

```
backend/
├── app.py                    # Application entry point
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
│
├── routes/                   # API endpoints
│   ├── __init__.py          # Route registration
│   ├── ocr.py               # OCR extraction endpoints
│   ├── chat.py              # Chat interface endpoints
│   ├── analytics.py         # Analytics endpoints
│   ├── database_query.py    # Query endpoints
│   ├── batch.py             # Batch processing
│   └── health.py            # Health check
│
├── ai/                       # AI agents and systems
│   ├── hybrid_query_engine.py    # Main orchestrator
│   ├── query_classifier.py       # Query classification
│   ├── sql_agent.py              # SQL generation
│   ├── rag_system.py             # RAG implementation
│   ├── analytics_orchestrator.py # Analytics coordinator
│   ├── pattern_detection.py      # Pattern analysis
│   ├── anomaly_detection.py      # Fraud detection
│   ├── forecasting_agent.py      # Forecasting
│   └── risk_assessment.py        # Risk analysis
│
├── models/                   # Database models
│   ├── __init__.py
│   └── database.py          # SQLAlchemy models
│
├── utils/                    # Utility functions
│   ├── openrouter.py        # LLM integration
│   ├── image_processing.py  # OCR processing
│   ├── analytics_service.py # Analytics helpers
│   ├── normalize.py         # Data normalization
│   └── save_transaction.py  # Transaction storage
│
├── instance/                 # Instance-specific files
│   └── lumen.db             # SQLite database
│
├── chroma_db/               # Vector database
│   └── chroma.sqlite3       # ChromaDB storage
│
└── uploads/                 # Uploaded files
```

### API Architecture

#### RESTful Endpoints

```python
# routes/__init__.py
def register_routes(app):
    """Register all route blueprints"""

    # OCR & Extraction
    app.register_blueprint(ocr_bp, url_prefix='/extract')

    # Chat Interface
    app.register_blueprint(chat_bp, url_prefix='/chat')

    # Analytics
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    # Database Queries
    app.register_blueprint(query_bp, url_prefix='/query')

    # Health Check
    app.register_blueprint(health_bp, url_prefix='/health')
```

#### Key Endpoints

| Endpoint               | Method | Description                      |
| ---------------------- | ------ | -------------------------------- |
| `/extract`             | POST   | Extract data from single invoice |
| `/extract-batch`       | POST   | Process multiple invoices        |
| `/chat`                | POST   | Natural language query           |
| `/chat/suggestions`    | GET    | Get query suggestions            |
| `/analytics/summary`   | GET    | Get spending summary             |
| `/analytics/trends`    | GET    | Get spending trends              |
| `/analytics/anomalies` | GET    | Get detected anomalies           |
| `/analytics/forecasts` | GET    | Get spending forecasts           |
| `/query`               | POST   | Execute database query           |
| `/health`              | GET    | Health check                     |

---

## 🤖 AI/ML Architecture

### Multi-Agent System

```
                    ┌──────────────────┐
                    │  User Query      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Query Classifier │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐   ┌──────────┐   ┌──────────┐
       │   SQL    │   │   RAG    │   │Analytics │
       │  Agent   │   │  System  │   │Orchestr. │
       └──────────┘   └──────────┘   └──────────┘
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                    ┌──────────────────┐
                    │  Hybrid Query    │
                    │     Engine       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Response       │
                    └──────────────────┘
```

### 1. Query Classifier

**Purpose**: Determine query type to route to appropriate agent

```python
class QueryClassifier:
    def classify(self, query: str) -> str:
        """
        Classify query into types:
        - ANALYTICAL: Requires database queries
        - CONVERSATIONAL: General questions
        - DOCUMENT: Specific to uploaded documents
        """
        # Use LLM to classify
        prompt = f"""
        Classify this query:
        "{query}"

        Categories:
        - ANALYTICAL: Data analysis, statistics, trends
        - CONVERSATIONAL: General questions, explanations
        - DOCUMENT: Specific document information
        """

        response = llm_call(prompt)
        return response['category']
```

### 2. SQL Agent

**Purpose**: Generate and execute SQL queries from natural language

```python
class SQLAgent:
    def query(self, user_query: str, user_id: str) -> dict:
        """
        Convert natural language to SQL
        Execute query
        Return results
        """
        # Get database schema
        schema = self.get_schema()

        # Generate SQL with LLM
        prompt = f"""
        Database Schema:
        {schema}

        User Query: {user_query}
        User ID: {user_id}

        Generate SQL query to answer the question.
        """

        sql = llm_generate_sql(prompt)

        # Execute query
        results = execute_sql(sql)

        # Format response
        return format_results(results)
```

### 3. RAG System

**Purpose**: Retrieve relevant documents and generate answers

```python
class RAGSystem:
    def __init__(self):
        self.vectorstore = ChromaDB()
        self.embeddings = SentenceTransformer()

    def query(self, user_query: str, user_id: str) -> dict:
        """
        Retrieve relevant documents
        Generate answer with context
        """
        # Generate query embedding
        query_embedding = self.embeddings.encode(user_query)

        # Retrieve similar documents
        docs = self.vectorstore.similarity_search(
            query_embedding,
            filter={'user_id': user_id},
            k=5
        )

        # Generate answer with context
        prompt = f"""
        Context: {docs}
        Question: {user_query}

        Answer the question using the context.
        """

        answer = llm_call(prompt)

        return {
            'answer': answer,
            'sources': docs
        }
```

### 4. Analytics Orchestrator

**Purpose**: Coordinate multiple analytics agents

```python
class AnalyticsOrchestrator:
    def __init__(self, db_path: str):
        self.pattern_agent = PatternDetectionAgent(db_path)
        self.anomaly_agent = FraudDetectionAgent(db_path)
        self.forecast_agent = ForecastingAgent(db_path)
        self.risk_agent = RiskAssessmentEngine(db_path)

    def analyze(self, user_id: str) -> dict:
        """
        Run all analytics agents
        Compile comprehensive report
        """
        results = {
            'patterns': self.pattern_agent.detect(user_id),
            'anomalies': self.anomaly_agent.detect(user_id),
            'forecasts': self.forecast_agent.predict(user_id),
            'risks': self.risk_agent.assess(user_id)
        }

        return self.compile_report(results)
```

### AI Agents Detail

#### Pattern Detection Agent

-   **Algorithm**: Time series analysis + clustering
-   **Features**: Seasonal patterns, spending habits, vendor patterns
-   **Output**: Identified patterns with confidence scores

#### Anomaly Detection Agent

-   **Algorithm**: Isolation Forest + Statistical methods
-   **Features**: Transaction amount, frequency, vendor, category
-   **Output**: Anomalous transactions with severity levels

#### Forecasting Agent

-   **Algorithm**: ARIMA + Prophet + ML ensemble
-   **Features**: Historical spending, seasonality, trends
-   **Output**: 3-month forecast with confidence intervals

#### Risk Assessment Engine

-   **Algorithm**: Rule-based + ML classification
-   **Features**: Vendor reliability, payment history, amount
-   **Output**: Risk scores and recommendations

---

## 💾 Database Architecture

### Entity-Relationship Diagram

```
┌─────────────────┐
│     Users       │
├─────────────────┤
│ id (PK)         │
│ username        │
│ email           │
│ created_at      │
└────────┬────────┘
         │
         │ 1:N
         │
┌────────▼────────────────┐
│     Invoices            │
├─────────────────────────┤
│ id (PK)                 │
│ user_id (FK)            │
│ vendor_name             │
│ invoice_number          │
│ invoice_date            │
│ due_date                │
│ total_amount            │
│ currency                │
│ payment_status          │
│ category                │
│ description             │
│ file_path               │
│ extracted_data (JSON)   │
│ created_at              │
│ updated_at              │
└─────────────────────────┘
```

### SQLAlchemy Models

```python
# models/database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)

    # Vendor Information
    vendor_name = db.Column(db.String(200))
    vendor_address = db.Column(db.Text)
    vendor_email = db.Column(db.String(100))
    vendor_phone = db.Column(db.String(20))

    # Invoice Details
    invoice_number = db.Column(db.String(100))
    invoice_date = db.Column(db.Date)
    due_date = db.Column(db.Date)

    # Financial Information
    subtotal = db.Column(db.Float)
    tax_amount = db.Column(db.Float)
    total_amount = db.Column(db.Float)
    currency = db.Column(db.String(3), default='USD')

    # Status & Classification
    payment_status = db.Column(db.String(20), default='pending')
    category = db.Column(db.String(50))

    # Additional Data
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    extracted_data = db.Column(db.JSON)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'vendor_name': self.vendor_name,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'total_amount': self.total_amount,
            'currency': self.currency,
            'payment_status': self.payment_status,
            'category': self.category,
            'created_at': self.created_at.isoformat()
        }
```

### Vector Database (ChromaDB)

```python
# Used for RAG system
# Stores document embeddings for semantic search

Collection Structure:
- documents: Invoice text content
- embeddings: 384-dim vectors (from sentence-transformers)
- metadata: {
    user_id: str,
    invoice_id: int,
    vendor: str,
    date: str,
    amount: float
  }
```

---

## 🔄 Data Flow

### 1. Invoice Upload & Processing

```
User Upload (Frontend)
        │
        ▼
    File Upload
        │
        ▼
POST /extract (Backend)
        │
        ├─→ Image Processing
        │   └─→ Google Vision API
        │       └─→ Extract Text
        │
        ├─→ Data Normalization
        │   └─→ Parse & Validate
        │
        ├─→ Database Storage
        │   └─→ Save Invoice
        │
        └─→ Vector Embedding
            └─→ Store in ChromaDB
                │
                ▼
        Return Success Response
                │
                ▼
        Frontend Updates UI
```

### 2. Natural Language Query

```
User Query (Frontend)
        │
        ▼
POST /chat (Backend)
        │
        ▼
Query Classifier
        │
    ┌───┴───┐
    │       │
    ▼       ▼
SQL Agent  RAG System
    │       │
    └───┬───┘
        │
        ▼
Hybrid Query Engine
        │
        ├─→ Execute Queries
        ├─→ Retrieve Documents
        └─→ Generate Response
            │
            ▼
    OpenRouter LLM
            │
            ▼
    Format Response
            │
            ▼
    Return to Frontend
            │
            ▼
    Display in Chat UI
```

### 3. Analytics Generation

```
Request Analytics (Frontend)
        │
        ▼
GET /analytics/* (Backend)
        │
        ▼
Analytics Orchestrator
        │
    ┌───┴───┬───────┬────────┐
    │       │       │        │
    ▼       ▼       ▼        ▼
Pattern Anomaly Forecast  Risk
 Agent   Agent    Agent   Agent
    │       │       │        │
    └───┬───┴───┬───┴────┬───┘
        │       │        │
        ▼       ▼        ▼
    Database Queries
        │
        ▼
    ML Processing
        │
        ▼
    Compile Results
        │
        ▼
    Return JSON
        │
        ▼
    Frontend Renders Charts
```

---

## 🔐 Security Architecture

### Authentication & Authorization

```python
# Current: User ID based
# Production: JWT tokens + OAuth2

from functools import wraps
from flask import request, jsonify

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401

        # Verify token
        user = verify_token(token)
        if not user:
            return jsonify({'error': 'Invalid token'}), 401

        return f(user, *args, **kwargs)
    return decorated
```

### Data Encryption

-   **In Transit**: HTTPS/TLS 1.3
-   **At Rest**: Database encryption (production)
-   **API Keys**: Environment variables, never committed
-   **File Uploads**: Sanitized and scanned

### Rate Limiting

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.headers.get('X-User-ID'),
    default_limits=["100 per hour"]
)

@app.route('/extract')
@limiter.limit("10 per minute")
def extract():
    # Heavy OCR processing
    pass
```

---

## 📈 Scalability Considerations

### Horizontal Scaling

-   **Frontend**: Static deployment on CDN
-   **Backend**: Multiple Flask instances behind load balancer
-   **Database**: Read replicas for analytics queries
-   **Vector DB**: Sharding by user_id

### Caching Strategy

```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0'
})

@app.route('/analytics/summary')
@cache.cached(timeout=300, query_string=True)
def get_summary():
    # Cache for 5 minutes
    return generate_summary()
```

### Background Jobs

```python
from celery import Celery

celery = Celery(app.name)

@celery.task
def process_batch_invoices(file_paths, user_id):
    """Process multiple invoices asynchronously"""
    results = []
    for path in file_paths:
        result = extract_invoice(path, user_id)
        results.append(result)
    return results
```

---

## 🧪 Testing Architecture

### Unit Tests

```python
# tests/test_sql_agent.py
import unittest
from ai.sql_agent import SQLAgent

class TestSQLAgent(unittest.TestCase):
    def setUp(self):
        self.agent = SQLAgent(':memory:')

    def test_query_generation(self):
        query = "Show all invoices"
        result = self.agent.query(query, 'test_user')
        self.assertIsNotNone(result)
```

### Integration Tests

```python
# tests/test_api.py
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

def test_extract_endpoint(client):
    response = client.post('/extract', data={
        'file': (io.BytesIO(b'test'), 'test.jpg'),
        'user_id': 'test'
    })
    assert response.status_code == 200
```

---

## 📊 Monitoring & Logging

### Logging Strategy

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@app.route('/extract')
def extract():
    logger.info(f"Processing invoice for user {user_id}")
    # ... processing ...
    logger.info(f"Invoice processed successfully")
```

### Metrics

-   Request latency
-   Error rates
-   OCR accuracy
-   Query response times
-   Database query performance
-   LLM API usage

---

## 🚀 Deployment Architecture

### Production Setup

```
         ┌─────────────┐
         │   Vercel    │
         │  (Frontend) │
         └──────┬──────┘
                │
                │ HTTPS
                │
         ┌──────▼──────┐
         │ Load Balancer│
         └──────┬──────┘
                │
        ┌───────┼───────┐
        │               │
   ┌────▼────┐    ┌────▼────┐
   │ Flask 1 │    │ Flask 2 │
   └────┬────┘    └────┬────┘
        │               │
        └───────┬───────┘
                │
        ┌───────┼───────┐
        │               │
   ┌────▼────┐    ┌────▼────┐
   │PostgreSQL│    │  Redis  │
   │ Primary  │    │  Cache  │
   └─────────┘    └─────────┘
```

### Environment Configuration

```bash
# Production .env
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/lumen
REDIS_URL=redis://host:6379/0
OPENROUTER_API_KEY=sk-...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json
SECRET_KEY=strong-random-key
CORS_ORIGINS=https://lumen.example.com
```

---

## 📚 API Documentation

Full API documentation available at `/docs` endpoint (Swagger/OpenAPI).

Example response formats documented in [API_DOCS.md](API_DOCS.md).

---

## 🔄 Future Enhancements

1. **Real-time Collaboration**: WebSocket support
2. **Mobile Apps**: React Native apps
3. **Email Integration**: Email invoice forwarding
4. **Advanced ML**: Custom trained models
5. **Multi-tenancy**: Organization management
6. **Audit Logs**: Complete audit trail
7. **Data Export**: Bulk export capabilities
8. **Integrations**: QuickBooks, Xero, SAP

---

<div align="center">

**Architecture designed for scale, security, and maintainability** 🏗️

</div>
