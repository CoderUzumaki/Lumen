# 🔆 LUMEN - AI-Powered Invoice Management System

<div align="center">

![LUMEN Logo](frontend/public/images/logo.png)

**Transforming Invoice Management with Artificial Intelligence**

[![Built for Hack-a-Sol](https://img.shields.io/badge/Built%20for-Hack--a--Sol-blue)](https://hackasol.iiit.ac.in)
[![IIIT Naya Raipur](https://img.shields.io/badge/IIIT-Naya%20Raipur-orange)](https://iiitnr.ac.in)
[![Team](https://img.shields.io/badge/Team-dUnder%20Pressure-green)](#team)

[📺 Demo Video](#demo) • [📋 Problem Statement](PROBLEM_STATEMENT.md) • [🚀 Quick Start](QUICK_START.md) • [📖 Documentation](DOCUMENTATION_INDEX.md)

</div>

---

## 📋 Table of Contents

-   [About](#about)
-   [Problem Statement](#problem-statement)
-   [Our Solution](#our-solution)
-   [Key Features](#key-features)
-   [Tech Stack](#tech-stack)
-   [Getting Started](#getting-started)
-   [Demo](#demo)
-   [Team](#team)
-   [Acknowledgments](#acknowledgments)

---

## 🎯 About

**LUMEN** is an intelligent invoice management system built for **Hack-a-Sol Hackathon** at **IIIT Naya Raipur** by **Team dUnder Pressure**. The project addresses the critical challenge of manual invoice processing in modern businesses by leveraging cutting-edge AI technologies.

### Built For

-   **Event**: Hack-a-Sol Hackathon
-   **Institution**: Indian Institute of Information Technology, Naya Raipur
-   **Team**: dUnder Pressure
-   **Challenge**: [View Problem Statement](PROBLEM_STATEMENT.md)

---

## 🔍 Problem Statement

> **See [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) for the complete problem statement.**

Manual invoice processing is a time-consuming, error-prone task that costs businesses significant resources. Finance teams spend 8+ hours weekly on:

-   Manual data entry from invoices
-   Cross-verification and validation
-   Payment tracking and reminders
-   Spending analysis and reporting
-   Fraud detection and compliance

**The Challenge**: Build an AI-powered solution that automates invoice processing, provides intelligent analytics, and enables natural language querying of financial data.

---

## 💡 Our Solution

LUMEN transforms invoice management through three core pillars:

### 1. 🤖 Intelligent OCR & Data Extraction

-   **95%+ accuracy** in invoice data extraction
-   Support for images, PDFs, and multi-page documents
-   Automatic validation and error detection
-   Real-time processing with instant feedback

### 2. 📊 AI-Powered Analytics

-   **Pattern Detection**: Identifies spending trends and seasonal patterns
-   **Anomaly Detection**: Flags suspicious transactions and potential fraud
-   **Forecasting**: Predicts future spending with ML models
-   **Risk Assessment**: Evaluates vendor and payment risks
-   **Smart Insights**: AI-generated recommendations for cost savings

### 3. 💬 Natural Language Query Interface

-   Ask questions in plain English
-   Hybrid SQL + RAG system for comprehensive answers
-   Context-aware responses with data citations
-   Query classification for optimal routing

---

## ✨ Key Features

### 🔐 Smart Invoice Processing

-   **Drag & Drop Upload**: Simple file upload interface
-   **Batch Processing**: Handle multiple invoices simultaneously
-   **Auto-validation**: Intelligent field validation
-   **Database Storage**: Secure PostgreSQL storage
-   **Export Options**: Excel, CSV, PDF reports

### 📈 Advanced Analytics Dashboard

-   **Real-time KPIs**: Annual spending, monthly averages, overdue payments
-   **Spending Trends**: Interactive graphs with forecasts
-   **Category Breakdown**: Pie charts and detailed analysis
-   **Payment Calendar**: Visual payment schedule
-   **Alert System**: Automated reminders and notifications

### 🤖 AI Assistant (Chatbot)

-   **Conversational Interface**: Natural language queries
-   **Multi-agent System**: SQL Agent + RAG System + Analytics Orchestrator
-   **Query Examples**:
    -   "Show me all invoices from last month"
    -   "Which vendor has the highest spending?"
    -   "Are there any unusual transactions?"
    -   "What's my projected spending for next quarter?"

### 🎨 Modern User Interface

-   **Dark Mode**: Elegant dark theme throughout
-   **Responsive Design**: Works on desktop, tablet, and mobile
-   **Animations**: Smooth Framer Motion animations
-   **Accessibility**: WCAG compliant components
-   **Intuitive Navigation**: Easy-to-use sidebar and breadcrumbs

---

## 🛠️ Tech Stack

### Frontend

-   **Framework**: Next.js 14.2.5 (React 18)
-   **Language**: TypeScript
-   **Styling**: Tailwind CSS
-   **UI Components**: Radix UI + Shadcn/ui
-   **Animations**: Framer Motion
-   **Charts**: Recharts
-   **Icons**: Lucide React, Tabler Icons
-   **HTTP Client**: Axios

### Backend

-   **Framework**: Flask 3.0.0
-   **Language**: Python 3.11+
-   **Database**: SQLite (dev) / PostgreSQL (production)
-   **ORM**: SQLAlchemy with Alembic migrations
-   **AI/ML**:
    -   OpenRouter API (LLM integration — vision model for OCR, text model for chat/analytics)
    -   ChromaDB (vector database)
    -   Scikit-learn (ML models)

### AI Agents

-   **Query Classifier**: Routes queries to appropriate systems
-   **SQL Agent**: Generates and executes SQL queries
-   **RAG System**: Retrieval-Augmented Generation for document Q&A
-   **Pattern Detection Agent**: Identifies spending patterns
-   **Anomaly Detection Agent**: Fraud and anomaly detection
-   **Forecasting Agent**: Time-series forecasting
-   **Risk Assessment Engine**: Vendor and payment risk analysis

### DevOps

-   **Version Control**: Git & GitHub
-   **API Testing**: Postman
-   **Environment**: Virtual environments (venv)
-   **CORS**: Flask-CORS for cross-origin requests

---

## 🚀 Getting Started

### Prerequisites

-   Node.js 18+ and npm
-   Python 3.11+
-   Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/CoderUzumaki/Lumen.git
cd Lumen
```

**📚 Complete Documentation:**

-   [Quick Start Guide](QUICK_START.md) - Get running in 5 minutes
-   [Detailed Setup Guide](SETUP.md) - Comprehensive installation instructions
-   [API Documentation](API_DOCS.md) - Complete API reference
-   [Architecture Guide](ARCHITECTURE.md) - Technical deep dive
-   [Deployment Guide](DEPLOYMENT.md) - Production deployment
-   [Contributing Guide](CONTRIBUTING.md) - How to contribute
-   [Documentation Index](DOCUMENTATION_INDEX.md) - Navigate all docs

---

## 🎥 Demo

### Video Demonstration

**📺 [Watch Full Demo on YouTube](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)**

> **Note**: Replace `YOUR_VIDEO_ID` with your actual YouTube video ID after uploading the demo.

**Demo Highlights**:

-   📄 Invoice upload and OCR extraction
-   📊 AI analytics dashboard walkthrough
-   💬 Natural language query examples
-   🚨 Anomaly detection in action
-   📈 Forecasting and insights
-   🎯 End-to-end workflow demonstration

### Live Screenshots

<details>
<summary>Click to view screenshots</summary>

#### Landing Page

![Landing Page](docs/screenshots/landing.png)

#### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

#### AI Analytics

![AI Analytics](docs/screenshots/ai-analytics.png)

#### Chat Interface

![Chat Interface](docs/screenshots/chatbot.png)

</details>

---

## 👥 Team

**Team dUnder Pressure**

Built with dedication by our amazing team for Hack-a-Sol @ IIIT Naya Raipur:

| Member              | Role                | Responsibilities                           | GitHub                                           |
| ------------------- | ------------------- | ------------------------------------------ | ------------------------------------------------ |
| Abhinav Mishra      | Full Stack Lead     | Frontend architecture, UI/UX, Landing page | [@CoderUzumaki](https://github.com/CoderUzumaki) |
| Nishant Borkar      | AI/ML Engineer      | AI agents, ML models, Analytics            | [@coderconnoisseur](https://github.com/coderconnoisseur)       |


---

## 🏆 Acknowledgments

### Special Thanks

-   **Hack-a-Sol Organizing Committee** at IIIT Naya Raipur
-   **Mentors and Judges** for their guidance and feedback
-   **Open Source Community** for the amazing tools and libraries

### Technologies & Services

-   [Next.js](https://nextjs.org/) - React framework
-   [Flask](https://flask.palletsprojects.com/) - Python web framework
-   [OpenRouter](https://openrouter.ai/) - LLM API gateway
-   [Google Cloud Vision](https://cloud.google.com/vision) - OCR API
-   [ChromaDB](https://www.trychroma.com/) - Vector database
-   [Vercel](https://vercel.com/) - Frontend hosting
-   [Render](https://render.com/) - Backend hosting

---

## 📄 License

This project was created for the Hack-a-Sol Hackathon at IIIT Naya Raipur.

---

## 📞 Contact

For questions or feedback about this project:

-   **Email**: team@dunder-pressure.dev
-   **GitHub Issues**: [Report a bug](https://github.com/CoderUzumaki/Lumen/issues)
-   **Project Maintainer**: [@CoderUzumaki](https://github.com/CoderUzumaki)

---

<div align="center">

**Built with ❤️ by Team dUnder Pressure for Hack-a-Sol @ IIIT Naya Raipur**

⭐ Star us on GitHub if you find this project helpful!

</div>
