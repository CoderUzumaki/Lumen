"""
Pattern Detection Agent - Identifies recurring patterns and spending habits
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
import json
import statistics

class PatternDetectionAgent:
    """Detects recurring patterns in transaction data"""
    
    def __init__(self, db_path: str):
        """
        Initialize pattern detection agent
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.frequency_windows = [7, 14, 30, 90, 365]  # days
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def detect_recurring_transactions(self, user_id: int, min_occurrences: int = 3) -> List[Dict]:
        """
        Detect recurring transactions (subscriptions, bills, etc.)
        
        Args:
            user_id: User ID to analyze
            min_occurrences: Minimum number of occurrences to consider a pattern
            
        Returns:
            List of detected patterns with metadata
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all transactions for user
        cursor.execute("""
            SELECT id, vendor_name, category, total_amount as amount, date as date
            FROM transactions
            WHERE user_id = ?
            ORDER BY date
        """, (user_id,))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if len(transactions) < min_occurrences:
            return []
        
        # Group by vendor and similar amounts (±10%)
        patterns = []
        
        # Group transactions by vendor
        vendor_groups = defaultdict(list)
        for txn in transactions:
            vendor_groups[txn['vendor_name']].append(txn)
        
        # Analyze each vendor group
        for vendor, txns in vendor_groups.items():
            if len(txns) < min_occurrences:
                continue
            
            # Sort by date
            txns.sort(key=lambda x: x['date'])
            
            # Calculate intervals between transactions
            intervals = []
            amounts = []
            
            for i in range(1, len(txns)):
                date1 = datetime.fromisoformat(txns[i-1]['date'])
                date2 = datetime.fromisoformat(txns[i]['date'])
                interval = (date2 - date1).days
                intervals.append(interval)
                amounts.append(txns[i].get('total_amount', txns[i].get('amount', 0)))
            
            if not intervals:
                continue
            
            # Check if intervals are consistent (±3 days tolerance)
            avg_interval = statistics.mean(intervals)
            interval_variance = statistics.stdev(intervals) if len(intervals) > 1 else 0
            
            # Consider it recurring if variance is low
            if interval_variance <= 5:  # Low variance = consistent pattern
                # Find closest standard frequency
                closest_freq = min(self.frequency_windows, 
                                 key=lambda x: abs(x - avg_interval))
                
                # Calculate confidence
                confidence = 1.0 - (interval_variance / avg_interval) if avg_interval > 0 else 0
                confidence = max(0.0, min(1.0, confidence))
                
                # Predict next occurrence
                last_date = datetime.fromisoformat(txns[-1]['date'])
                next_predicted = last_date + timedelta(days=int(avg_interval))
                
                # Average amount
                avg_amount = statistics.mean(amounts) if amounts else txns[0].get('total_amount', txns[0].get('amount', 0))
                amount_variance = statistics.stdev(amounts) if len(amounts) > 1 else 0
                
                pattern = {
                    'pattern_type': 'recurring',
                    'vendor_name': vendor,
                    'category': txns[0]['category'],
                    'frequency_days': int(avg_interval),
                    'closest_frequency': closest_freq,
                    'average_amount': round(avg_amount, 2),
                    'amount_variance': round(amount_variance, 2),
                    'occurrence_count': len(txns),
                    'confidence_score': round(confidence, 3),
                    'last_occurrence': txns[-1]['date'],
                    'next_predicted_date': next_predicted.date().isoformat(),
                    'intervals': intervals,
                    'transaction_ids': [t['id'] for t in txns]
                }
                
                patterns.append(pattern)
        
        return patterns
    
    def detect_day_of_month_patterns(self, user_id: int) -> List[Dict]:
        """
        Detect patterns like "groceries on 10th of month"
        
        Args:
            user_id: User ID to analyze
            
        Returns:
            List of day-of-month patterns
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT vendor_name, category, date, total_amount as amount
            FROM transactions
            WHERE user_id = ?
            ORDER BY date
        """, (user_id,))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Group by category
        category_groups = defaultdict(list)
        for txn in transactions:
            date = datetime.fromisoformat(txn['date'])
            day_of_month = date.day
            txn['day_of_month'] = day_of_month
            category_groups[txn['category']].append(txn)
        
        patterns = []
        
        for category, txns in category_groups.items():
            if len(txns) < 3:
                continue
            
            # Count occurrences by day of month
            day_counts = defaultdict(int)
            for txn in txns:
                day_counts[txn['day_of_month']] += 1
            
            # Find dominant days (>= 3 occurrences)
            for day, count in day_counts.items():
                if count >= 3:
                    # Calculate next occurrence
                    today = datetime.now()
                    next_occurrence = datetime(today.year, today.month, day)
                    
                    if next_occurrence <= today:
                        # Move to next month
                        if today.month == 12:
                            next_occurrence = datetime(today.year + 1, 1, day)
                        else:
                            next_occurrence = datetime(today.year, today.month + 1, day)
                    
                    pattern = {
                        'pattern_type': 'day_of_month',
                        'category': category,
                        'day_of_month': day,
                        'occurrence_count': count,
                        'confidence_score': min(count / len(txns), 1.0),
                        'next_predicted_date': next_occurrence.date().isoformat(),
                        'description': f"You typically spend on {category} around the {day}th"
                    }
                    
                    patterns.append(pattern)
        
        return patterns
    
    def save_patterns_to_db(self, user_id: int, patterns: List[Dict]):
        """
        Save detected patterns to database
        
        Args:
            user_id: User ID
            patterns: List of detected patterns
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create patterns table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spending_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pattern_type VARCHAR(50),
                vendor_name VARCHAR(255),
                category VARCHAR(100),
                frequency_days INTEGER,
                average_amount REAL,
                amount_variance REAL,
                last_occurrence DATE,
                next_predicted_date DATE,
                confidence_score REAL,
                occurrence_count INTEGER,
                is_active BOOLEAN DEFAULT 1,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Clear old patterns for this user
        cursor.execute("DELETE FROM spending_patterns WHERE user_id = ?", (user_id,))
        
        # Insert new patterns
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO spending_patterns 
                (user_id, pattern_type, vendor_name, category, frequency_days,
                 average_amount, amount_variance, last_occurrence, next_predicted_date,
                 confidence_score, occurrence_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                pattern['pattern_type'],
                pattern.get('vendor_name'),
                pattern.get('category'),
                pattern.get('frequency_days'),
                pattern.get('average_amount'),
                pattern.get('amount_variance'),
                pattern.get('last_occurrence'),
                pattern['next_predicted_date'],
                pattern['confidence_score'],
                pattern.get('occurrence_count', 0),
                json.dumps(pattern)
            ))
        
        conn.commit()
        conn.close()
        
        return len(patterns)
    
    def generate_reminders(self, user_id: int, days_ahead: int = 7) -> List[Dict]:
        """
        Generate smart reminders based on patterns
        
        Args:
            user_id: User ID
            days_ahead: Look ahead this many days
            
        Returns:
            List of reminders
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM spending_patterns
            WHERE user_id = ?
            AND is_active = 1
            AND confidence_score >= 0.6
        """, (user_id,))
        
        patterns = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        reminders = []
        today = datetime.now().date()
        future_date = today + timedelta(days=days_ahead)
        
        for pattern in patterns:
            next_date = datetime.fromisoformat(pattern['next_predicted_date']).date()
            
            # Check if predicted date is within our window
            if today <= next_date <= future_date:
                days_until = (next_date - today).days
                
                # Generate reminder text
                if pattern['pattern_type'] == 'recurring':
                    if days_until == 0:
                        reminder_text = f"Your {pattern['vendor_name']} payment is typically due today"
                    elif days_until == 1:
                        reminder_text = f"Your {pattern['vendor_name']} payment is typically due tomorrow"
                    else:
                        reminder_text = f"Your {pattern['vendor_name']} payment is typically due in {days_until} days"
                    
                    # Add amount info
                    if pattern['average_amount']:
                        reminder_text += f" (approximately ₹{pattern['average_amount']:.0f})"
                
                elif pattern['pattern_type'] == 'day_of_month':
                    day = pattern.get('day_of_month', next_date.day)
                    reminder_text = f"You usually buy {pattern['category']} around the {day}th — time to restock!"
                
                else:
                    reminder_text = f"Reminder about {pattern.get('category', 'transaction')}"
                
                reminder = {
                    'title': f"Upcoming: {pattern.get('vendor_name') or pattern.get('category')}",
                    'description': reminder_text,
                    'reminder_type': 'pattern_based',
                    'predicted_date': next_date.isoformat(),
                    'days_until': days_until,
                    'confidence_score': pattern['confidence_score'],
                    'pattern_id': pattern['id'],
                    'metadata': pattern
                }
                
                reminders.append(reminder)
        
        return reminders
    
    def analyze_user(self, user_id: int) -> Dict[str, Any]:
        """
        Complete pattern analysis for a user
        
        Args:
            user_id: User ID to analyze
            
        Returns:
            Analysis results with patterns and reminders
        """
        print(f"🔍 Analyzing patterns for user {user_id}...")
        
        # Detect recurring transactions
        recurring = self.detect_recurring_transactions(user_id)
        print(f"   Found {len(recurring)} recurring patterns")
        
        # Detect day-of-month patterns
        dom_patterns = self.detect_day_of_month_patterns(user_id)
        print(f"   Found {len(dom_patterns)} day-of-month patterns")
        
        # Combine all patterns
        all_patterns = recurring + dom_patterns
        
        # Save to database
        saved = self.save_patterns_to_db(user_id, all_patterns)
        print(f"   Saved {saved} patterns to database")
        
        # Generate reminders
        reminders = self.generate_reminders(user_id, days_ahead=7)
        print(f"   Generated {len(reminders)} reminders")
        
        return {
            'user_id': user_id,
            'patterns_detected': len(all_patterns),
            'recurring_patterns': len(recurring),
            'day_of_month_patterns': len(dom_patterns),
            'active_reminders': len(reminders),
            'patterns': all_patterns,
            'reminders': reminders
        }


# Test the pattern detection agent
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pattern_detection_agent.py <db_path> [user_id]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    agent = PatternDetectionAgent(db_path)
    
    print("="*60)
    print("Pattern Detection Agent Test")
    print("="*60)
    
    results = agent.analyze_user(user_id)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    print(f"\nTotal Patterns: {results['patterns_detected']}")
    print(f"Recurring: {results['recurring_patterns']}")
    print(f"Day-of-Month: {results['day_of_month_patterns']}")
    print(f"Active Reminders: {results['active_reminders']}")
    
    print("\n" + "-"*60)
    print("RECURRING PATTERNS:")
    print("-"*60)
    for pattern in results['patterns'][:5]:
        if pattern['pattern_type'] == 'recurring':
            print(f"\n✓ {pattern['vendor_name']}")
            print(f"  Frequency: Every {pattern['frequency_days']} days")
            print(f"  Average Amount: ₹{pattern['average_amount']}")
            print(f"  Confidence: {pattern['confidence_score']:.1%}")
            print(f"  Next Predicted: {pattern['next_predicted_date']}")
    
    print("\n" + "-"*60)
    print("REMINDERS:")
    print("-"*60)
    for reminder in results['reminders'][:5]:
        print(f"\n📅 {reminder['title']}")
        print(f"   {reminder['description']}")
        print(f"   In {reminder['days_until']} days ({reminder['predicted_date']})")
        print(f"   Confidence: {reminder['confidence_score']:.1%}")