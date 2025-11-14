# rag_system.py

import chromadb
from chromadb.utils import embedding_functions
import requests
import os
from typing import List, Dict, Any
import json
class RAGSystem:
    """Semantic search over transaction descriptions"""
    
    def __init__(self, collection_name: str = "transactions"):
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path="./chroma_db")
        
        # Use OpenAI-compatible embeddings via OpenRouter
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv('OPENROUTER_API_KEY'),
            api_base="https://openrouter.ai/api/v1",
            model_name="openai/text-embedding-3-small"
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function
        )
    
    def add_transaction(self, transaction: Dict[str, Any]):
        """Add a transaction to vector store"""
        # Create searchable text from transaction
        searchable_text = self._create_searchable_text(transaction)
        
        # Add to ChromaDB with user_id in metadata for filtering
        self.collection.add(
            documents=[searchable_text],
            metadatas=[{
                'transaction_id': str(transaction['id']),
                'user_id': str(transaction['user_id']),
                'vendor_name': str(transaction['vendor_name'] or ''),
                'category': str(transaction.get('category') or 'Other'),
                'amount': str(transaction.get('total_amount', 0)),
                'date': str(transaction.get('date', ''))
            }],
            ids=[f"txn_{transaction['id']}"]
        )
        print(f"✅ Added transaction {transaction['id']} to ChromaDB")
    
    def _create_searchable_text(self, transaction: Dict[str, Any]) -> str:
        """Create rich text representation for embedding"""
        items_text = ""
        if transaction.get('items'):
            items = transaction['items']
            if isinstance(items, str):
                items = json.loads(items)
            if isinstance(items, list):
                items_text = ", ".join([item.get('item_name', '') for item in items])
        
        text = f"""
        Date: {transaction.get('date', 'Unknown')}
        Vendor: {transaction.get('vendor_name', 'Unknown')}
        Category: {transaction.get('category', 'Other')}
        Amount: {transaction.get('total_amount', 0)} INR
        Items: {items_text}
        Payment: {transaction.get('payment_method', 'Unknown')}
        Invoice: {transaction.get('invoice_number', '')}
        Address: {transaction.get('address', '')}
        """
        
        return text.strip()
    
    def search(self, query: str, user_id: str, n_results: int = 5) -> List[Dict]:
        """Semantic search for transactions"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": str(user_id)}  # Ensure user_id is string
        )
        
        return results
    
    def search_with_filter(self, 
                          query: str, 
                          user_id: str,
                          category: str = None,
                          date_from: str = None,
                          n_results: int = 5) -> List[Dict]:
        """Semantic search with metadata filters"""
        where_clause = {"user_id": str(user_id)}
        
        if category:
            where_clause["category"] = category
        
        if date_from:
            where_clause["date"] = {"$gte": date_from}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        return results