# sql_agent.py

import requests
import sqlite3
import json
from typing import Dict, Any
import os
class SQLAgent:
    """Converts natural language to SQL and executes queries"""
    
    def __init__(self, db_path: str = "instance/lumen.db"):
        """Initialize SQLAgent with SQLite database"""
        self.db_path = db_path
        
    SQL_GENERATION_PROMPT = """
    You are an expert SQL query generator for a financial transactions database using SQLite.
    
    Database Schema:
    - Table: transactions
    - Columns:
      * id (TEXT) - UUID as string
      * user_id (TEXT) - UUID as string
      * date (TEXT) - Date as string in YYYY-MM-DD format
      * total_amount (REAL)
      * tax_amount (REAL)
      * vendor_name (TEXT)
      * invoice_number (TEXT)
      * category (TEXT) - Values: Groceries, Restaurant, Utilities, Transport, Healthcare, Shopping, Entertainment, Other
      * payment_method (TEXT)
      * address (TEXT)
      * created_at (TEXT) - Timestamp
    
    - Table: transaction_items
    - Columns:
      * id (TEXT) - UUID as string
      * transaction_id (TEXT) - Foreign key
      * item_name (TEXT)
      * quantity (INTEGER)
      * unit_price (REAL)
      * total_price (REAL)
    
    Rules:
    1. ALWAYS include user_id filter (user_id = '{user_id}')
    2. Use SQLite date functions (date(), datetime(), strftime())
    3. Return ONLY the SQL query, no explanation
    4. Use LIMIT to prevent huge results
    5. For aggregations, use appropriate GROUP BY
    6. Handle NULL values gracefully
    7. Use single quotes for string literals
    8. UUIDs are stored as TEXT strings
    
    User Question: {query}
    Current Date: {current_date}
    
    Generate SQL query:
    """
    
    def generate_sql(self, query: str, user_id: int) -> str:
        """Generate SQL from natural language"""
        from datetime import datetime
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-3.5-sonnet",
                    "messages": [
                        {
                            "role": "user",
                            "content": self.SQL_GENERATION_PROMPT.format(
                                query=query,
                                user_id=user_id,
                                current_date=datetime.now().strftime('%Y-%m-%d')
                            )
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 500
                }
            )
            
            result = response.json()
            
            # Check for API errors
            if 'error' in result:
                print(f"OpenRouter API error in SQL generation: {result['error']}")
                # Return a basic SELECT query as fallback
                return f"SELECT * FROM transactions WHERE user_id = '{user_id}' LIMIT 10"
            
            sql = result['choices'][0]['message']['content'].strip()
            
            # Clean up markdown formatting
            sql = sql.replace('```sql', '').replace('```', '').strip()
            
            return sql
            
        except Exception as e:
            print(f"Error generating SQL: {e}")
            # Return a safe default query
            return f"SELECT * FROM transactions WHERE user_id = '{user_id}' LIMIT 10"
    
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL and return results using SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch results
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            results = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'data': results,
                'row_count': len(results)
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def query(self, natural_language_query: str, user_id: str) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Results"""
        sql = self.generate_sql(natural_language_query, user_id)
        results = self.execute_sql(sql)
        results['sql'] = sql
        return results