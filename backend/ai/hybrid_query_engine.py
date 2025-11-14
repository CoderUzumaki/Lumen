# hybrid_query_engine.py

from query_classifier import QueryClassifier
from sql_agent import SQLAgent
from rag_system import RAGSystem
import requests
import os
from typing import Dict, Any
import json
class HybridQueryEngine:
    """Orchestrates SQL Agent and RAG System"""
    
    def __init__(self, db_connection_string: str):
        self.classifier = QueryClassifier()
        self.sql_agent = SQLAgent(db_connection_string)
        self.rag_system = RAGSystem()
    
    def query(self, user_query: str, user_id: int) -> Dict[str, Any]:
        """
        Main entry point for all queries
        Routes to appropriate system and synthesizes response
        """
        # Step 1: Classify query
        query_type = self.classifier.classify(user_query)
        
        print(f"Query classified as: {query_type}")
        
        # Step 2: Execute appropriate system
        if query_type == 'ANALYTICAL':
            results = self.sql_agent.query(user_query, user_id)
            context_type = 'sql'
        else:
            results = self.rag_system.search(user_query, user_id)
            context_type = 'semantic'
        
        # Step 3: Synthesize response
        response = self._synthesize_response(
            user_query=user_query,
            results=results,
            context_type=context_type
        )
        
        return {
            'query': user_query,
            'query_type': query_type,
            'raw_results': results,
            'response': response
        }
    
    def _synthesize_response(self, 
                            user_query: str, 
                            results: Dict, 
                            context_type: str) -> str:
        """Generate natural language response from results"""
        
        synthesis_prompt = f"""
        You are a financial assistant explaining query results to a user.
        
        User asked: "{user_query}"
        
        Query type: {context_type}
        
        Results:
        {json.dumps(results, indent=2, default=str)}
        
        Generate a clear, concise answer:
        1. Directly answer the question
        2. Include key numbers/facts
        3. Add brief insight if relevant
        4. Keep it conversational
        
        Answer:
        """
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": synthesis_prompt}],
                "temperature": 0.7,
                "max_tokens": 500
            }
        )
        
        return response.json()['choices'][0]['message']['content']