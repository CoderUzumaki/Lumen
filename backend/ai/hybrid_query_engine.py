# hybrid_query_engine.py
import json
import logging
from typing import Dict, Any

import requests

from config import Config

from .query_classifier import QueryClassifier
from .sql_agent import SQLAgent
from .rag_system import RAGSystem

logger = logging.getLogger(__name__)


class HybridQueryEngine:
    """Orchestrates SQL Agent and RAG System"""

    def __init__(self, db_path: str | None = None):
        resolved = db_path or str(Config.DATABASE_PATH)
        self.classifier = QueryClassifier()
        self.sql_agent = SQLAgent(resolved)
        self.rag_system = RAGSystem()
    
    def query(self, user_query: str, user_id: str) -> Dict[str, Any]:
        """
        Main entry point for all queries
        Routes to appropriate system and synthesizes response
        """
        # Step 1: Classify query
        query_type = self.classifier.classify(user_query)
        
        logger.info(f"Query classified as: {query_type}")
        
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
        
        try:
            response = requests.post(
                Config.OPENROUTER_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": Config.get_llm_text_model(),
                    "messages": [{"role": "user", "content": synthesis_prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
            
            response_data = response.json()
            
            # Log response for debugging
            logger.info(f"OpenRouter response status: {response.status_code}")
            if response.status_code != 200:
                logger.info(f"OpenRouter error: {response_data}")
                return f"Error generating response: {response_data.get('error', {}).get('message', 'Unknown error')}"
            
            return response_data['choices'][0]['message']['content']
        
        except KeyError as e:
            logger.info(f"KeyError in response: {e}")
            logger.info(f"Full response: {response_data}")
            return "Error: Unable to generate natural language response. Raw results available in 'raw_results' field."
        except Exception as e:
            logger.info(f"Error synthesizing response: {e}")
            return f"Error generating response: {str(e)}"