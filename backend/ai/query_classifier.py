# query_classifier.py

import requests
import os

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

class QueryClassifier:
    """Classifies user queries into ANALYTICAL or SEMANTIC"""
    
    CLASSIFICATION_PROMPT = """
    You are a query classifier for a financial intelligence system.
    
    Classify the following user query into ONE of these types:
    
    1. ANALYTICAL - Requires SQL/aggregation/filtering:
       - Questions with: sum, total, average, count, most, least, top, bottom
       - Comparisons: more than, less than, between
       - Time-based: monthly, weekly, last month, this year
       - Aggregations: group by category, by vendor, by date
       
    2. SEMANTIC - Requires similarity/context search:
       - Descriptive: "show me", "find", "what did I buy"
       - Context-based: "at Starbucks", "coffee purchases"
       - Similar to: "like this", "similar transactions"
       - Vague: "tell me about", "search for"
    
    User Query: {query}
    
    Respond with ONLY one word: ANALYTICAL or SEMANTIC
    """
    
    def classify(self, query: str) -> str:
        """
        Classify query type
        Returns: 'ANALYTICAL' or 'SEMANTIC'
        """
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [
                    {
                        "role": "user",
                        "content": self.CLASSIFICATION_PROMPT.format(query=query)
                    }
                ],
                "temperature": 0,
                "max_tokens": 10
            }
        )
        
        result = response.json()
        classification = result['choices'][0]['message']['content'].strip().upper()
        
        # Fallback to ANALYTICAL if unclear
        if classification not in ['ANALYTICAL', 'SEMANTIC']:
            classification = 'ANALYTICAL'
        
        return classification