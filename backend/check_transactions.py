"""
Check what transactions exist in database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Transaction
import collections

with app.app_context():
    txns = Transaction.query.filter_by(user_id='123').all()
    print(f'Total transactions for user 123: {len(txns)}')
    
    if txns:
        dates = [t.date for t in txns]
        print(f'Date range: {min(dates)} to {max(dates)}')
        
        months = collections.Counter([d[:7] for d in dates])
        print('\nTransactions by month:')
        for month, count in sorted(months.items()):
            total = sum(t.total_amount for t in txns if t.date.startswith(month))
            print(f'  {month}: {count} transactions, ${total:.2f} total')
    else:
        print('No transactions found!')
