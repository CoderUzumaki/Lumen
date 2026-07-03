# rag_system.py
import json
import logging
from typing import List, Dict, Any

import requests

from config import Config

logger = logging.getLogger(__name__)


class RAGSystem:
    """Semantic search over transaction descriptions."""

    def __init__(self, collection_name: str = "transactions"):
        self.enabled = Config.ENABLE_CHROMA
        self.collection = None

        if not self.enabled:
            logger.info("ChromaDB disabled (ENABLE_CHROMA=false)")
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self.client = chromadb.PersistentClient(path=str(Config.CHROMA_DB_PATH))
            self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=Config.OPENROUTER_API_KEY,
                api_base=Config.OPENROUTER_BASE_URL,
                model_name=Config.LLM_EMBEDDING_MODEL,
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
            )
        except Exception as e:
            logger.warning("ChromaDB unavailable: %s", e)
            self.enabled = False
            self.collection = None

    def add_transaction(self, transaction: Dict[str, Any]):
        if not self.collection:
            return

        searchable_text = self._create_searchable_text(transaction)
        self.collection.add(
            documents=[searchable_text],
            metadatas=[
                {
                    "transaction_id": str(transaction["id"]),
                    "user_id": str(transaction["user_id"]),
                    "vendor_name": str(transaction["vendor_name"] or ""),
                    "category": str(transaction.get("category") or "Other"),
                    "amount": str(transaction.get("total_amount", 0)),
                    "date": str(transaction.get("date", "")),
                }
            ],
            ids=[f"txn_{transaction['id']}"],
        )

    def _create_searchable_text(self, transaction: Dict[str, Any]) -> str:
        items_text = ""
        if transaction.get("items"):
            items = transaction["items"]
            if isinstance(items, str):
                items = json.loads(items)
            if isinstance(items, list):
                items_text = ", ".join(
                    [item.get("item_name", "") for item in items]
                )

        return f"""
        Date: {transaction.get('date', 'Unknown')}
        Vendor: {transaction.get('vendor_name', 'Unknown')}
        Category: {transaction.get('category', 'Other')}
        Amount: {transaction.get('total_amount', 0)} INR
        Items: {items_text}
        Payment: {transaction.get('payment_method', 'Unknown')}
        Invoice: {transaction.get('invoice_number', '')}
        Address: {transaction.get('address', '')}
        """.strip()

    def search(self, query: str, user_id: str, n_results: int = 5) -> Dict:
        if not self.collection:
            return {
                "success": False,
                "error": "Semantic search is unavailable",
                "data": [],
            }

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": str(user_id)},
        )
        return {"success": True, "data": results}

    def search_with_filter(
        self,
        query: str,
        user_id: str,
        category: str = None,
        date_from: str = None,
        n_results: int = 5,
    ) -> Dict:
        if not self.collection:
            return {
                "success": False,
                "error": "Semantic search is unavailable",
                "data": [],
            }

        where_clause: dict = {"user_id": str(user_id)}
        if category:
            where_clause["category"] = category
        if date_from:
            where_clause["date"] = {"$gte": date_from}

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause,
        )
        return {"success": True, "data": results}
