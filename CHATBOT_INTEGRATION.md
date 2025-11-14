# Chatbot Integration Guide

## Overview
The chatbot has been integrated with the backend chat API to enable AI-powered financial queries.

## Backend Setup

### 1. Start the Backend Server
```bash
cd backend
# Activate virtual environment
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Mac/Linux

# Run the server
python app.py
```

The backend will start on `http://localhost:5000`

### 2. Backend Endpoints

#### Chat Endpoint
- **URL**: `POST /chat`
- **Body**:
  ```json
  {
    "query": "Where did I spend most last month?",
    "user_id": "1"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "answer": "AI response here...",
      "sql": "SELECT ...",
      "results": []
    }
  }
  ```

#### Suggestions Endpoint
- **URL**: `GET /chat/suggestions`
- **Response**:
  ```json
  {
    "suggestions": [
      "Where did I spend the most last month?",
      "Show me all grocery purchases",
      ...
    ]
  }
  ```

## Frontend Setup

### 1. Start the Frontend
```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:3000`

### 2. Navigate to Chatbot
Go to: `http://localhost:3000/chatbot`

## Features

### 1. **Suggested Questions**
When you open a new chat, you'll see 4 suggested questions that you can click to ask immediately.

### 2. **Real-time AI Responses**
- Type any financial question
- The chatbot will show a "thinking" indicator
- AI response appears from the backend

### 3. **Error Handling**
If the backend is not running, you'll see an error message:
"Sorry, I encountered an error. Please make sure the backend server is running and try again."

## API Integration Details

### Files Modified

1. **`frontend/src/lib/api/client.ts`**
   - Added `chatApi` with two methods:
     - `sendMessage(query, userId)`
     - `getSuggestions()`

2. **`frontend/src/app/chatbot/aiAssistantUI.tsx`**
   - Imported `chatApi`
   - Updated `sendMessage()` to call backend API
   - Added `suggestions` state
   - Loads suggestions on component mount
   - Handles errors gracefully

3. **`frontend/src/components/chatbot/ChatPane.tsx`**
   - Added `suggestions` prop
   - Displays suggested questions in empty state
   - Questions are clickable and auto-fill the chat

## Testing

### Test the Integration:

1. **Start both servers** (backend on :5000, frontend on :3000)
2. **Navigate to** `/chatbot`
3. **Click a suggested question** or type your own
4. **Verify**:
   - Loading indicator appears
   - AI response is displayed
   - Response comes from the backend (check backend logs)

### Backend Test (Direct API):
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me my expenses", "user_id": "1"}'
```

## Troubleshooting

### "Cannot connect to backend"
- Ensure backend is running on port 5000
- Check `NEXT_PUBLIC_BACKEND_URL` in frontend `.env`
- Default: `http://localhost:5000`

### "No suggestions appearing"
- Check browser console for errors
- Verify `/chat/suggestions` endpoint returns data
- Check network tab in browser DevTools

### Backend errors
- Check backend console for Python errors
- Ensure all dependencies are installed
- Verify database connection

## Next Steps

1. **Add Authentication**: Currently uses hardcoded `user_id: "1"`
2. **Improve Error Messages**: More specific error handling
3. **Add Streaming**: For real-time token-by-token responses
4. **Conversation History**: Save conversations to database
5. **Context Awareness**: Multi-turn conversations with memory
