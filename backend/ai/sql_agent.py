# sql_agent.py

import requests
import psycopg2
import json
from typing import Dict, Any
import os
class SQLAgent:
    """Converts natural language to SQL and executes queries"""
    
    def __init__(self, db_connection_string: str):
        self.conn = psycopg2.connect(db_connection_string)
        
    SQL_GENERATION_PROMPT = """
    You are an expert SQL query generator for a financial transactions database.
    
    Database Schema:
    - Table: transactions
    - Columns:
      * id (INTEGER)
      * user_id (INTEGER)
      * transaction_date (DATE)
      * amount (DECIMAL)
      * vendor_name (VARCHAR)
      * category (VARCHAR) - Values: Groceries, Restaurant, Utilities, Transport, Healthcare, Shopping, Entertainment, Other
      * payment_method (VARCHAR)
      * items (JSONB) - Array of items
      * description (TEXT)
    
    Rules:
    1. ALWAYS include user_id filter (user_id = {user_id})
    2. Use proper date functions for time-based queries
    3. Return ONLY the SQL query, no explanation
    4. Use LIMIT to prevent huge results
    5. For aggregations, use appropriate GROUP BY
    6. Handle NULL values gracefully
    
    User Question: {query}
    Current Date: {current_date}
    
    Generate SQL query:
    """
    
    def generate_sql(self, query: str, user_id: int) -> str:
        """Generate SQL from natural language"""
        from datetime import datetime
        
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
        sql = result['choices'][0]['message']['content'].strip()
        
        # Clean up markdown formatting
        sql = sql.replace('```sql', '').replace('```', '').strip()
        
        return sql
    
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL and return results"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            
            # Fetch results
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            results = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            
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
    
    def query(self, natural_language_query: str, user_id: int) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Results"""
        sql = self.generate_sql(natural_language_query, user_id)
        results = self.execute_sql(sql)
        results['sql'] = sql
        return results