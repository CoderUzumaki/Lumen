# hybrid_query_engine.py
import json
import logging
from typing import Dict, Any

from config import Config
from utils.llm import chat_completion

from .query_classifier import QueryClassifier
from .sql_agent import SQLAgent
from .rag_system import RAGSystem

logger = logging.getLogger(__name__)


class HybridQueryEngine:
    """Orchestrates SQL Agent and RAG System"""

    def __init__(self, db_path: str | None = None):
        # db_path=None -> the app database (Postgres on Render, SQLite locally).
        self.classifier = QueryClassifier()
        self.sql_agent = SQLAgent(db_path)
        self.rag_system = RAGSystem()
    
    def query(self, user_query: str, user_id: str) -> Dict[str, Any]:
        """Classify the question, fetch matching data, and write the answer.

        Raises utils.llm.LLMError when the LLM provider can't be used (bad key,
        no credits, rate limit, outage, retired model); the route turns that
        into a user-facing error rather than a fake answer.
        """
        if not getattr(self.rag_system, "enabled", False):
            # A SEMANTIC label would fall back to SQL anyway (see below), so
            # classifying here would only cost latency and quota.
            query_type = 'ANALYTICAL'
            logger.info("Semantic search disabled; answering with SQL without classifying")
        else:
            query_type = self.classifier.classify(user_query)
            logger.info("Query classified as: %s", query_type)

        results = None
        context_type = 'sql'
        if query_type == 'SEMANTIC':
            results = self._semantic_search(user_query, user_id)
            context_type = 'semantic'
        if results is None:
            # Analytical question, or semantic search unavailable.
            results = self.sql_agent.query(user_query, user_id)
            context_type = 'sql'

        response = self._synthesize_response(
            user_query=user_query,
            results=results,
            context_type=context_type,
        )

        return {
            'query': user_query,
            'query_type': query_type,
            'raw_results': results,
            'response': response,
        }

    def _semantic_search(self, user_query: str, user_id: str) -> Dict[str, Any] | None:
        """Vector search, or None if the index can't serve it (disabled, not
        built, embedding call failed) so the caller can use SQL instead."""
        try:
            results = self.rag_system.search(user_query, user_id)
        except Exception as e:
            logger.warning("Semantic search failed (%s); falling back to SQL", e)
            return None
        if not results.get("success"):
            logger.info("Semantic search unavailable (%s); falling back to SQL", results.get("error"))
            return None
        return results

    def _synthesize_response(self,
                            user_query: str,
                            results: Dict,
                            context_type: str) -> str:
        """Generate natural language response from results"""

        synthesis_prompt = f"""
        You are a financial assistant explaining query results to a user.
        Amounts are in {Config.DEFAULT_CURRENCY} unless the data says otherwise.

        User asked: "{user_query}"

        Query type: {context_type}

        Results:
        {json.dumps(results, default=str, ensure_ascii=False, separators=(",", ":"))}

        Generate a clear, concise answer:
        1. Directly answer the question
        2. Include key numbers/facts
        3. Add brief insight if relevant
        4. Keep it conversational
        5. If the results are empty, say you found no matching transactions and
           suggest uploading invoices; do not invent data

        Answer:
        """

        return chat_completion(synthesis_prompt, temperature=0.7, max_tokens=500)