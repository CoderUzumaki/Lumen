from models.database import db
from models import Transaction
from sqlalchemy import func, and_
from datetime import datetime, timedelta

class AnalyticsService:

    @staticmethod
    def total_spending(user_id):
        res = db.session.query(
            func.sum(Transaction.total_amount)
        ).filter_by(user_id=user_id).scalar()

        return float(res or 0)

    @staticmethod
    def monthly_spending(user_id):
        """Group by YYYY-MM using string LIKE"""
        rows = db.session.query(
            func.substr(Transaction.date, 1, 7).label("month"),
            func.sum(Transaction.total_amount)
        ).filter_by(user_id=user_id)\
         .group_by("month")\
         .order_by("month")\
         .all()

        return [
            {"month": month, "spend": float(amount)} 
            for month, amount in rows
        ]

    @staticmethod
    def category_breakdown(user_id):
        rows = db.session.query(
            Transaction.category,
            func.sum(Transaction.total_amount)
        ).filter_by(user_id=user_id)\
         .group_by(Transaction.category)\
         .all()

        return [
            {"category": cat, "spend": float(amount)} 
            for cat, amount in rows
        ]

    @staticmethod
    def vendor_breakdown(user_id):
        rows = db.session.query(
            Transaction.vendor_name,
            func.sum(Transaction.total_amount)
        ).filter_by(user_id=user_id)\
         .group_by(Transaction.vendor_name)\
         .order_by(func.sum(Transaction.total_amount).desc())\
         .limit(10)\
         .all()

        return [
            {"vendor": v, "spend": float(amount)} 
            for v, amount in rows
        ]

    @staticmethod
    def _get_period_stats(user_id, start_date, end_date):
        """Get statistics for a specific time period"""
        transactions = Transaction.query.filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.date >= start_date,
                Transaction.date <= end_date
            )
        ).all()

        if not transactions:
            return {
                "average_spending": 0.0,
                "max_spending": 0.0,
                "min_spending": 0.0,
                "total_spending": 0.0,
                "transaction_count": 0
            }

        amounts = [t.total_amount for t in transactions if t.total_amount]
        total = sum(amounts)
        count = len(amounts)

        return {
            "average_spending": round(total / count, 2) if count > 0 else 0.0,
            "max_spending": round(max(amounts), 2) if amounts else 0.0,
            "min_spending": round(min(amounts), 2) if amounts else 0.0,
            "total_spending": round(total, 2),
            "transaction_count": count
        }

    @staticmethod
    def _get_week_range(year, week):
        """Get start and end date for a given week number"""
        # Week 1 starts on the first Monday of the year
        jan_first = datetime(year, 1, 1)
        # Find the first Monday
        days_until_monday = (7 - jan_first.weekday()) % 7
        first_monday = jan_first + timedelta(days=days_until_monday)
        
        # Calculate the start of the requested week
        week_start = first_monday + timedelta(weeks=week - 1)
        week_end = week_start + timedelta(days=6)
        
        return week_start.date(), week_end.date()

    @staticmethod
    def get_time_range_analytics(user_id, time_range, year, month=None, week=None):
        """
        Get analytics for a specific time range with comparison to previous period
        
        Args:
            user_id: User ID
            time_range: "weekly", "monthly", or "yearly"
            year: Year (e.g., 2025)
            month: Month (0-11, optional for monthly)
            week: Week number (1-52, optional for weekly)
        """
        current_label = ""
        current_start = None
        current_end = None
        previous_start = None
        previous_end = None
        previous_label = ""

        # Calculate date ranges based on time_range
        if time_range == "yearly":
            current_label = f"{year}"
            current_start = datetime(year, 1, 1).date()
            current_end = datetime(year, 12, 31).date()
            
            previous_label = f"{year - 1}"
            previous_start = datetime(year - 1, 1, 1).date()
            previous_end = datetime(year - 1, 12, 31).date()

        elif time_range == "monthly":
            if month is None:
                raise ValueError("month parameter required for monthly time_range")
            
            # Convert 0-11 to 1-12 for datetime
            month_num = month + 1
            
            month_names = ["January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"]
            current_label = f"{month_names[month]} {year}"
            
            current_start = datetime(year, month_num, 1).date()
            
            # Calculate last day of month
            if month_num == 12:
                current_end = datetime(year, 12, 31).date()
            else:
                current_end = (datetime(year, month_num + 1, 1) - timedelta(days=1)).date()
            
            # Previous month
            if month_num == 1:
                prev_month_num = 12
                prev_year = year - 1
            else:
                prev_month_num = month_num - 1
                prev_year = year
            
            previous_label = f"{month_names[prev_month_num - 1]} {prev_year}"
            previous_start = datetime(prev_year, prev_month_num, 1).date()
            
            if prev_month_num == 12:
                previous_end = datetime(prev_year, 12, 31).date()
            else:
                previous_end = (datetime(prev_year, prev_month_num + 1, 1) - timedelta(days=1)).date()

        elif time_range == "weekly":
            if week is None:
                raise ValueError("week parameter required for weekly time_range")
            
            current_start, current_end = AnalyticsService._get_week_range(year, week)
            current_label = f"Week {week}, {year}"
            
            # Previous week
            if week == 1:
                previous_start, previous_end = AnalyticsService._get_week_range(year - 1, 52)
                previous_label = f"Week 52, {year - 1}"
            else:
                previous_start, previous_end = AnalyticsService._get_week_range(year, week - 1)
                previous_label = f"Week {week - 1}, {year}"

        else:
            raise ValueError(f"Invalid time_range: {time_range}. Must be 'weekly', 'monthly', or 'yearly'")

        # Get statistics for current and previous periods
        current_stats = AnalyticsService._get_period_stats(user_id, current_start, current_end)
        previous_stats = AnalyticsService._get_period_stats(user_id, previous_start, previous_end)

        # Calculate comparison metrics
        def calc_percent_change(current, previous):
            if previous == 0:
                return 0.0 if current == 0 else 100.0
            return round(((current - previous) / previous) * 100, 2)

        comparison = {
            "avg_change_percent": calc_percent_change(
                current_stats["average_spending"], 
                previous_stats["average_spending"]
            ),
            "max_change_percent": calc_percent_change(
                current_stats["max_spending"], 
                previous_stats["max_spending"]
            ),
            "min_change_percent": calc_percent_change(
                current_stats["min_spending"], 
                previous_stats["min_spending"]
            ),
            "total_change_amount": round(
                current_stats["total_spending"] - previous_stats["total_spending"], 2
            ),
            "total_change_percent": calc_percent_change(
                current_stats["total_spending"], 
                previous_stats["total_spending"]
            )
        }

        return {
            "success": True,
            "current_period": {
                "label": current_label,
                "start_date": current_start.isoformat(),
                "end_date": current_end.isoformat(),
                **current_stats
            },
            "previous_period": {
                "label": previous_label,
                "start_date": previous_start.isoformat(),
                "end_date": previous_end.isoformat(),
                **previous_stats
            },
            "comparison": comparison
        }
