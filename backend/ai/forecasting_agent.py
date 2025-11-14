"""
Forecasting Agent - Predicts future spending using time-series analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
import requests
import os
from models.database import db

class ForecastingAgent:
    """Time-series forecasting for spending predictions"""
    
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
    
    def __init__(self):
        """
        Initialize forecasting agent
        """
        pass
    
    def get_historical_data(self, user_id: int, days_back: int = 180) -> pd.DataFrame:
        """
        Get historical spending data
        
        Args:
            user_id: User ID
            days_back: Number of days to look back
            
        Returns:
            DataFrame with daily aggregated spending
        """
        cutoff_date = (datetime.now() - timedelta(days=days_back)).date().isoformat()
        
        query = db.text("""
            SELECT 
                date as date,
                SUM(total_amount) as total_amount,
                COUNT(*) as transaction_count,
                category
            FROM transactions
            WHERE user_id = :user_id
            AND date >= :cutoff_date
            GROUP BY date, category
            ORDER BY date
        """)
        
        df = pd.read_sql_query(query, db.session.connection(), params={'user_id': str(user_id), 'cutoff_date': cutoff_date})
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def simple_moving_average(self, data: pd.Series, window: int = 7) -> pd.Series:
        """Calculate simple moving average"""
        return data.rolling(window=window, min_periods=1).mean()
    
    def exponential_smoothing(self, data: pd.Series, alpha: float = 0.3) -> pd.Series:
        """Exponential smoothing for trend"""
        result = [data.iloc[0]]
        for i in range(1, len(data)):
            result.append(alpha * data.iloc[i] + (1 - alpha) * result[-1])
        return pd.Series(result, index=data.index)
    
    def calculate_trend(self, data: pd.Series) -> str:
        """
        Determine spending trend
        
        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        if len(data) < 10:
            return 'stable'
        
        # Compare first half vs second half
        mid_point = len(data) // 2
        first_half_mean = data[:mid_point].mean()
        second_half_mean = data[mid_point:].mean()
        
        change_percent = ((second_half_mean - first_half_mean) / first_half_mean * 100) if first_half_mean > 0 else 0
        
        if change_percent > 10:
            return 'increasing'
        elif change_percent < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def forecast_spending(self, user_id: int, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Forecast future spending
        
        Args:
            user_id: User ID
            days_ahead: Number of days to forecast
            
        Returns:
            Forecast results with predictions
        """
        print(f"📊 Forecasting spending for user {user_id}...")
        
        # Get historical data
        df = self.get_historical_data(user_id, days_back=90)
        
        if df.empty or len(df) < 10:
            return {
                'user_id': user_id,
                'success': False,
                'message': 'Insufficient historical data for forecasting'
            }
        
        # Aggregate by date (sum all categories)
        daily_spending = df.groupby('date')['total_amount'].sum()
        
        # Fill missing dates with 0
        date_range = pd.date_range(start=daily_spending.index.min(), 
                                   end=daily_spending.index.max(), 
                                   freq='D')
        daily_spending = daily_spending.reindex(date_range, fill_value=0)
        
        print(f"   Analyzing {len(daily_spending)} days of data")
        
        # Calculate statistics
        mean_daily = daily_spending.mean()
        median_daily = daily_spending.median()
        std_daily = daily_spending.std()
        
        # Calculate trend
        trend = self.calculate_trend(daily_spending)
        
        # Simple forecast using exponential smoothing
        smoothed = self.exponential_smoothing(daily_spending, alpha=0.3)
        last_value = smoothed.iloc[-1]
        
        # Adjust for trend
        if trend == 'increasing':
            growth_rate = 1.05  # 5% increase
        elif trend == 'decreasing':
            growth_rate = 0.95  # 5% decrease
        else:
            growth_rate = 1.0
        
        # Generate forecasts
        forecast_dates = []
        forecast_values = []
        forecast_lower = []
        forecast_upper = []
        
        current_date = daily_spending.index[-1]
        current_value = last_value
        
        for i in range(1, days_ahead + 1):
            forecast_date = current_date + timedelta(days=i)
            
            # Simple forecast with trend adjustment
            forecast_value = current_value * growth_rate
            
            # Add some day-of-week seasonality
            if forecast_date.weekday() >= 5:  # Weekend
                forecast_value *= 1.1  # Slightly higher on weekends
            
            # Confidence intervals (±20%)
            lower = forecast_value * 0.8
            upper = forecast_value * 1.2
            
            forecast_dates.append(forecast_date.strftime('%Y-%m-%d'))
            forecast_values.append(round(forecast_value, 2))
            forecast_lower.append(round(lower, 2))
            forecast_upper.append(round(upper, 2))
            
            current_value = forecast_value
        
        # Calculate total forecasted spending
        total_forecast = sum(forecast_values)
        
        # Category-wise forecast
        category_forecast = self.forecast_by_category(user_id, days_ahead)
        
        # Generate insights using LLM
        insights = self.generate_forecast_insights(
            mean_daily=mean_daily,
            total_forecast=total_forecast,
            trend=trend,
            days_ahead=days_ahead,
            category_forecast=category_forecast
        )
        
        return {
            'user_id': user_id,
            'success': True,
            'forecast_period_days': days_ahead,
            'historical_stats': {
                'mean_daily': round(mean_daily, 2),
                'median_daily': round(median_daily, 2),
                'std_daily': round(std_daily, 2),
                'total_last_30_days': round(daily_spending[-30:].sum(), 2) if len(daily_spending) >= 30 else 0
            },
            'trend': trend,
            'forecast': {
                'dates': forecast_dates,
                'values': forecast_values,
                'lower_bound': forecast_lower,
                'upper_bound': forecast_upper,
                'total_predicted': round(total_forecast, 2)
            },
            'category_forecast': category_forecast,
            'insights': insights
        }
    
    def forecast_by_category(self, user_id: int, days_ahead: int = 30) -> List[Dict]:
        """Forecast spending by category"""
        # Get last 90 days per category
        query = db.text("""
            SELECT 
                category,
                AVG(daily_amount) as avg_daily,
                SUM(daily_amount) as total_90days
            FROM (
                SELECT 
                    category,
                    date,
                    SUM(total_amount) as daily_amount
                FROM transactions
                WHERE user_id = :user_id
                AND date >= date('now', '-90 days')
                GROUP BY category, date
            )
            GROUP BY category
            ORDER BY total_90days DESC
        """)
        
        result = db.session.execute(query, {'user_id': str(user_id)})
        results = result.fetchall()
        
        category_forecasts = []
        for row in results:
            category, avg_daily, total_90 = row
            predicted_total = avg_daily * days_ahead
            
            category_forecasts.append({
                'category': category,
                'avg_daily': round(avg_daily, 2),
                'predicted_total': round(predicted_total, 2)
            })
        
        return category_forecasts
    
    def generate_forecast_insights(self, 
                                   mean_daily: float, 
                                   total_forecast: float,
                                   trend: str,
                                   days_ahead: int,
                                   category_forecast: List[Dict]) -> List[str]:
        """Generate human-readable insights using LLM"""
        
        if not self.OPENROUTER_API_KEY:
            return [
                f"Your daily spending average is ₹{mean_daily:.0f}",
                f"Predicted spending for next {days_ahead} days: ₹{total_forecast:.0f}",
                f"Trend: {trend}"
            ]
        
        # Prepare context for LLM
        top_categories = category_forecast[:3]
        category_text = ", ".join([f"{c['category']} (₹{c['predicted_total']:.0f})" 
                                  for c in top_categories])
        
        prompt = f"""You are a financial advisor analyzing spending forecasts.

Historical Data:
- Daily average spending: ₹{mean_daily:.0f}
- Spending trend: {trend}

Forecast (next {days_ahead} days):
- Predicted total: ₹{total_forecast:.0f}
- Top categories: {category_text}

Generate 3-4 concise, actionable insights (1 sentence each):
1. Overall spending prediction
2. Trend observation
3. Category-specific advice
4. Actionable recommendation

Return as JSON array of strings:
["insight 1", "insight 2", ...]
"""
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 300
                },
                timeout=30
            )
            
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON
            content = content.replace('```json', '').replace('```', '').strip()
            insights = json.loads(content)
            
            return insights
        
        except Exception as e:
            print(f"LLM insight generation failed: {str(e)}")
            return [
                f"Based on your spending pattern, expect around ₹{total_forecast:.0f} in the next {days_ahead} days.",
                f"Your spending trend is {trend}.",
                f"Top spending category: {top_categories[0]['category']}" if top_categories else "Monitor your expenses."
            ]


# Test/Example Usage
if __name__ == "__main__":
    print("="*60)
    print("Forecasting Agent Module")
    print("="*60)
    print("\n⚠️  This module should be imported and used within the Flask app context.")
    print("\n📘 Example usage:")
    print("""
    from flask import Flask
    from models.database import init_db
    from ai.forecasting_agent import ForecastingAgent
    
    # Use the existing Flask app from app.py
    with app.app_context():
        agent = ForecastingAgent()
        results = agent.forecast_spending(user_id=123, days_ahead=30)
        if results['success']:
            print(f"30-day forecast: ₹{results['forecast']['total_predicted']:.0f}")
    """)
    print("\n✅ See app.py for proper Flask application initialization.")
    print("="*60)