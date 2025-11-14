# query_classifier.py

import requests
import os

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

class QueryClassifier:
    """Classifies user queries into ANALYTICAL or SEMANTIC"""
    
    CLASSIFICATION_PROMPT = """
    You are a query classifier for a financial intelligence system.
    
    Classify the following user query into ONE of these types:
    
    1. ANALYTICAL - Requires SQL/aggregation/filtering/listing:
       - List queries: "list all", "show all", "get all"
       - Questions with: sum, total, average, count, most, least, top, bottom
       - Comparisons: more than, less than, between
       - Time-based: monthly, weekly, last month, this year
       - Aggregations: group by category, by vendor, by date
       - IMPORTANT: "list all transactions" is ANALYTICAL
       
    2. SEMANTIC - Requires similarity/context/semantic search:
       - Context-based: "at Starbucks", "coffee purchases"
       - Similar to: "like this", "similar transactions"
       - Vague/fuzzy: "tell me about", "search for", "find things related to"
       - When user doesn't specify exact criteria
    
    User Query: {query}
    
    Think step by step:
    - Does the query ask for ALL items or need SQL listing? → ANALYTICAL
    - Does the query need aggregation (sum, count, average)? → ANALYTICAL  
    - Does the query need semantic similarity search? → SEMANTIC
    
    Respond with ONLY one word: ANALYTICAL or SEMANTIC
    """
    
    def classify(self, query: str) -> str:
        """
        Classify query type
        Returns: 'ANALYTICAL' or 'SEMANTIC'
        """
        # Rule-based pre-check for obvious analytical queries
        query_lower = query.lower()
        analytical_keywords = [
            'list all', 'show all', 'get all', 'all transactions',
            'sum', 'total', 'average', 'count', 'how many',
            'most', 'least', 'top', 'bottom',
            'more than', 'less than', 'between',
            'monthly', 'weekly', 'last month', 'this year',
            'group by', 'aggregate'
        ]
        
        # Check for obvious analytical patterns
        for keyword in analytical_keywords:
            if keyword in query_lower:
                print(f"🎯 Quick match: '{keyword}' found → ANALYTICAL")
                return 'ANALYTICAL'
        
        # Otherwise, use LLM classification
        try:
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
            
            # Check for errors in response
            if 'error' in result:
                print(f"OpenRouter API error in classifier: {result['error']}")
                return 'ANALYTICAL'  # Default fallback
            
            raw_response = result['choices'][0]['message']['content'].strip()
            classification = raw_response.upper()
            
            print(f"🔍 Query: '{query}'")
            print(f"📊 LLM raw response: '{raw_response}'")
            print(f"✅ Classification: {classification}")
            
            # Fallback to ANALYTICAL if unclear
            if classification not in ['ANALYTICAL', 'SEMANTIC']:
                print(f"⚠️  Invalid classification '{classification}', defaulting to ANALYTICAL")
                classification = 'ANALYTICAL'
            
            return classification
            
        except Exception as e:
            print(f"Error in query classifier: {e}")
            print(f"Defaulting to ANALYTICAL query type")
            return 'ANALYTICAL'  # Safe fallback