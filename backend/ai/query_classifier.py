# query_classifier.py
import logging

from utils.llm import LLMError, chat_completion

logger = logging.getLogger(__name__)

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
                logger.info(f"🎯 Quick match: '{keyword}' found → ANALYTICAL")
                return 'ANALYTICAL'
        
        # Otherwise, use LLM classification
        try:
            raw_response = chat_completion(
                self.CLASSIFICATION_PROMPT.format(query=query),
                temperature=0,
                max_tokens=20,
            )
        except LLMError as e:
            if e.is_fatal:
                # Auth/credits/rate-limit/outage: every later step would fail too.
                raise
            logger.warning("Classifier got an unusable reply (%s); defaulting to ANALYTICAL", e)
            return 'ANALYTICAL'

        classification = raw_response.upper()
        # Models sometimes wrap the label in punctuation or a sentence.
        for label in ('ANALYTICAL', 'SEMANTIC'):
            if label in classification:
                return label
        logger.warning("Unrecognised classification %r, defaulting to ANALYTICAL", raw_response)
        return 'ANALYTICAL'