# 📡 API Documentation

Complete API reference for LUMEN backend services.

---

## Base URL

-   **Development**: `http://localhost:5000`
-   **Production**: `https://api.lumen.example.com`

---

## Authentication

Currently using user_id based authentication. Future versions will implement JWT tokens.

```bash
# Include user_id in request body or query parameter
user_id=your_user_id
```

---

## Endpoints

### 🏥 Health Check

#### GET `/health`

Check API health status.

**Response:**

```json
{
	"status": "healthy",
	"timestamp": "2025-11-15T10:30:00Z",
	"version": "1.0.0"
}
```

---

### 📄 Invoice Extraction

#### POST `/extract`

Extract data from a single invoice image/PDF.

**Request:**

```bash
POST /extract
Content-Type: multipart/form-data

file: <binary file data>
user_id: "user123"
```

**Response:**

```json
{
	"success": true,
	"message": "Invoice extracted and saved successfully",
	"data": {
		"invoice_id": 42,
		"vendor_name": "TechCorp Solutions",
		"invoice_number": "INV-2025-001",
		"invoice_date": "2025-01-15",
		"due_date": "2025-02-15",
		"total_amount": 1250.0,
		"currency": "USD",
		"category": "Software",
		"line_items": [
			{
				"description": "Software License",
				"quantity": 1,
				"unit_price": 1000.0,
				"amount": 1000.0
			}
		],
		"subtotal": 1000.0,
		"tax_amount": 250.0
	},
	"processing_time": 2.3
}
```

**Error Response:**

```json
{
	"error": "No file uploaded",
	"code": "MISSING_FILE"
}
```

---

#### POST `/extract-batch`

Process multiple invoices from a multi-page PDF.

**Request:**

```bash
POST /extract-batch
Content-Type: multipart/form-data

file: <PDF file data>
user_id: "user123"
```

**Response:**

```json
{
	"success": true,
	"message": "Batch processing completed",
	"total_pages": 5,
	"successful": 4,
	"failed": 1,
	"results": [
		{
			"page": 1,
			"status": "success",
			"invoice_id": 43,
			"vendor_name": "VendorA"
		},
		{
			"page": 2,
			"status": "failed",
			"error": "Low quality image"
		}
	],
	"processing_time": 8.7
}
```

---

### 💬 Chat Interface

#### POST `/chat`

Send natural language query to AI assistant.

**Request:**

```json
POST /chat
Content-Type: application/json

{
  "query": "Show me all invoices from last month",
  "user_id": "user123",
  "conversation_id": "conv_456" // optional
}
```

**Response:**

```json
{
	"success": true,
	"response": "I found 12 invoices from last month (October 2025). Here's a summary:\n\n- Total spending: $24,567.89\n- Average invoice: $2,047.32\n- Top vendor: TechCorp ($8,900.00)\n\nWould you like to see more details?",
	"data": {
		"invoices": [
			{
				"id": 35,
				"vendor": "TechCorp",
				"amount": 8900.0,
				"date": "2025-10-15"
			}
		],
		"total": 24567.89,
		"count": 12
	},
	"query_type": "ANALYTICAL",
	"sources": [
		{
			"type": "database",
			"query": "SELECT * FROM invoices WHERE ..."
		}
	],
	"conversation_id": "conv_456"
}
```

---

#### GET `/chat/suggestions`

Get sample query suggestions for users.

**Response:**

```json
{
	"suggestions": [
		"Show me all invoices from last month",
		"What's my total spending this year?",
		"Which vendor has the highest spending?",
		"Are there any overdue payments?",
		"Show me software category invoices",
		"What's my average monthly spending?",
		"Detect any unusual transactions",
		"Forecast my spending for next quarter"
	]
}
```

---

### 📊 Analytics

#### GET `/analytics/summary`

Get comprehensive spending summary.

**Request:**

```bash
GET /analytics/summary?user_id=user123&period=all
```

**Query Parameters:**

-   `user_id` (required): User identifier
-   `period` (optional): `month`, `quarter`, `year`, `all` (default: `all`)
-   `start_date` (optional): Start date (YYYY-MM-DD)
-   `end_date` (optional): End date (YYYY-MM-DD)

**Response:**

```json
{
	"success": true,
	"summary": {
		"total_invoices": 156,
		"total_spending": 245680.5,
		"average_invoice": 1575.52,
		"currency": "USD",
		"period": {
			"start": "2024-01-01",
			"end": "2025-11-15"
		}
	},
	"by_status": {
		"paid": {
			"count": 140,
			"amount": 230450.0
		},
		"pending": {
			"count": 12,
			"amount": 12430.5
		},
		"overdue": {
			"count": 4,
			"amount": 2800.0
		}
	},
	"by_category": {
		"Software": 87240.0,
		"Office Supplies": 46748.0,
		"Cloud Services": 41765.85,
		"Utilities": 34427.65,
		"Equipment": 22100.0,
		"Others": 13399.0
	},
	"top_vendors": [
		{
			"name": "TechCorp Solutions",
			"invoice_count": 24,
			"total_amount": 65400.0
		}
	]
}
```

---

#### GET `/analytics/trends`

Get spending trends over time.

**Request:**

```bash
GET /analytics/trends?user_id=user123&granularity=monthly&period=12
```

**Query Parameters:**

-   `user_id` (required): User identifier
-   `granularity`: `daily`, `weekly`, `monthly` (default: `monthly`)
-   `period`: Number of periods to analyze (default: 12)

**Response:**

```json
{
	"success": true,
	"trends": [
		{
			"period": "2024-12",
			"total": 18450.0,
			"invoice_count": 8,
			"average": 2306.25
		},
		{
			"period": "2025-01",
			"total": 22340.5,
			"invoice_count": 12,
			"average": 1861.71
		}
	],
	"growth": {
		"percentage": 12.5,
		"direction": "up"
	},
	"forecast": [
		{
			"period": "2025-12",
			"predicted": 24500.0,
			"confidence_interval": {
				"lower": 22000.0,
				"upper": 27000.0
			}
		}
	]
}
```

---

#### GET `/analytics/anomalies`

Get detected anomalies and suspicious transactions.

**Request:**

```bash
GET /analytics/anomalies?user_id=user123&severity=all
```

**Query Parameters:**

-   `user_id` (required): User identifier
-   `severity`: `high`, `medium`, `low`, `all` (default: `all`)
-   `limit`: Maximum results (default: 50)

**Response:**

```json
{
	"success": true,
	"anomalies": [
		{
			"id": 1,
			"invoice_id": 142,
			"type": "amount_spike",
			"severity": "high",
			"description": "Invoice amount significantly higher than average",
			"details": {
				"amount": 45000.0,
				"average_for_vendor": 2500.0,
				"deviation": 1700.0
			},
			"detected_at": "2025-11-10T14:30:00Z",
			"vendor": "NewVendor Inc",
			"recommendation": "Review this transaction for accuracy"
		},
		{
			"id": 2,
			"invoice_id": 138,
			"type": "duplicate",
			"severity": "medium",
			"description": "Possible duplicate invoice",
			"details": {
				"similar_to": 135,
				"similarity": 0.95
			},
			"detected_at": "2025-11-08T09:15:00Z"
		}
	],
	"summary": {
		"total": 8,
		"high": 2,
		"medium": 4,
		"low": 2
	}
}
```

---

#### GET `/analytics/forecasts`

Get spending forecasts based on historical data.

**Request:**

```bash
GET /analytics/forecasts?user_id=user123&months=3
```

**Query Parameters:**

-   `user_id` (required): User identifier
-   `months`: Forecast period (default: 3)
-   `category`: Specific category (optional)

**Response:**

```json
{
	"success": true,
	"forecasts": [
		{
			"period": "2025-12",
			"predicted_spending": 23450.0,
			"confidence_interval": {
				"lower": 21000.0,
				"upper": 26000.0
			},
			"confidence_score": 0.85
		},
		{
			"period": "2026-01",
			"predicted_spending": 24100.0,
			"confidence_interval": {
				"lower": 21500.0,
				"upper": 27000.0
			},
			"confidence_score": 0.82
		}
	],
	"model_info": {
		"algorithm": "ARIMA + Prophet Ensemble",
		"accuracy": 0.92,
		"trained_on": "156 historical invoices"
	},
	"insights": [
		"Spending trend is increasing by ~3% monthly",
		"Seasonal peak expected in Q1 2026",
		"Software category showing highest growth"
	]
}
```

---

#### GET `/analytics/patterns`

Get detected spending patterns.

**Request:**

```bash
GET /analytics/patterns?user_id=user123
```

**Response:**

```json
{
	"success": true,
	"patterns": {
		"recurring": [
			{
				"vendor": "CloudHost Inc",
				"frequency": "monthly",
				"average_amount": 499.0,
				"next_expected": "2025-12-01",
				"confidence": 0.98
			}
		],
		"seasonal": [
			{
				"category": "Marketing",
				"pattern": "Q4 spike",
				"increase_percentage": 45.0,
				"description": "Marketing spending increases 45% in Q4"
			}
		],
		"spending_habits": {
			"preferred_vendors": ["TechCorp", "OfficeMax", "CloudHost"],
			"peak_spending_day": "Monday",
			"average_invoice_age": 12.5
		}
	}
}
```

---

#### GET `/analytics/risk-assessment`

Get risk assessment for vendors and payments.

**Request:**

```bash
GET /analytics/risk-assessment?user_id=user123
```

**Response:**

```json
{
	"success": true,
	"risk_assessment": {
		"overall_risk": "low",
		"risk_score": 2.3,
		"vendors": [
			{
				"vendor": "NewVendor Inc",
				"risk_level": "medium",
				"risk_score": 5.7,
				"factors": [
					"New vendor (< 3 months)",
					"Large transaction amount",
					"Limited transaction history"
				],
				"recommendations": [
					"Verify vendor credentials",
					"Start with smaller amounts"
				]
			}
		],
		"payment_risks": [
			{
				"invoice_id": 145,
				"risk_type": "late_payment",
				"risk_level": "high",
				"days_overdue": 15,
				"amount": 3200.0
			}
		]
	}
}
```

---

### 🔍 Database Queries

#### POST `/query`

Execute direct database queries (with validation).

**Request:**

```json
POST /query
Content-Type: application/json

{
  "query": "SELECT vendor_name, SUM(total_amount) FROM invoices WHERE user_id = ? GROUP BY vendor_name",
  "user_id": "user123",
  "params": ["user123"]
}
```

**Response:**

```json
{
	"success": true,
	"results": [
		{
			"vendor_name": "TechCorp",
			"total": 65400.0
		}
	],
	"row_count": 15,
	"execution_time": 0.045
}
```

---

## Error Codes

| Code                  | Description                     |
| --------------------- | ------------------------------- |
| `MISSING_FILE`        | No file provided in upload      |
| `INVALID_FILE_TYPE`   | File type not supported         |
| `OCR_FAILED`          | OCR extraction failed           |
| `INVALID_USER_ID`     | User ID not provided or invalid |
| `DATABASE_ERROR`      | Database operation failed       |
| `INVALID_QUERY`       | Invalid or malicious query      |
| `API_LIMIT_EXCEEDED`  | Rate limit exceeded             |
| `INVALID_DATE_FORMAT` | Date format incorrect           |
| `UNAUTHORIZED`        | Authentication failed           |

---

## Rate Limits

-   **OCR Extraction**: 10 requests per minute
-   **Chat Queries**: 30 requests per minute
-   **Analytics**: 60 requests per minute
-   **General**: 100 requests per minute

**Rate Limit Headers:**

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1699875600
```

---

## Webhooks (Future)

Receive notifications for events:

-   `invoice.processed` - Invoice successfully processed
-   `payment.overdue` - Payment is overdue
-   `anomaly.detected` - Anomaly detected in transaction
-   `forecast.updated` - New forecast available

---

## SDKs & Libraries

### Python Client

```python
from lumen_client import LumenClient

client = LumenClient(api_key='your_api_key')

# Upload invoice
result = client.extract_invoice('path/to/invoice.pdf', user_id='user123')

# Query
response = client.chat('Show me all invoices', user_id='user123')

# Get analytics
analytics = client.get_analytics_summary(user_id='user123')
```

### JavaScript/TypeScript Client

```typescript
import { LumenClient } from "@lumen/client";

const client = new LumenClient({ apiKey: "your_api_key" });

// Upload invoice
const result = await client.extractInvoice(file, { userId: "user123" });

// Query
const response = await client.chat("Show me all invoices", {
	userId: "user123",
});

// Get analytics
const analytics = await client.getAnalyticsSummary({ userId: "user123" });
```

---

## Testing

### Postman Collection

Import the Postman collection: [Download](./postman_collection.json)

### cURL Examples

```bash
# Extract invoice
curl -X POST http://localhost:5000/extract \
  -F "file=@invoice.pdf" \
  -F "user_id=test_user"

# Chat query
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show all invoices", "user_id": "test_user"}'

# Get analytics
curl http://localhost:5000/analytics/summary?user_id=test_user
```

---

## Changelog

### v1.0.0 (Current)

-   Initial API release
-   OCR extraction
-   Chat interface
-   Analytics endpoints
-   Batch processing

---

<div align="center">

**Need help?** Check our [Setup Guide](SETUP.md) or [Architecture Docs](ARCHITECTURE.md)

</div>
