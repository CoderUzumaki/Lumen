from flask import Blueprint, g, request, jsonify

from utils.analytics_service import AnalyticsService
from utils.auth import require_auth

analytics_bp = Blueprint("analytics_bp", __name__)


@analytics_bp.route("/analytics/summary", methods=["GET", "OPTIONS"])
@require_auth
def analytics_summary():
    """
    Get analytics summary with time-range based filtering. Identity comes
    from the JWT (g.user_id); no user_id query param is read.

    Query Parameters:
    - time_range: "weekly" | "monthly" | "yearly" (optional)
    - year: number (required if time_range is provided)
    - month: number (optional, 0-11 for monthly time_range)
    - week: number (optional, 1-52 for weekly time_range)
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return jsonify({}), 200

    user_id = g.user_id

    # Check if time_range parameter is provided (new behavior)
    time_range = request.args.get("time_range")
    
    if time_range:
        # New behavior: time-range based analytics with comparison
        try:
            year = request.args.get("year", type=int)
            if not year:
                return jsonify({"error": "year required when time_range is specified"}), 400
            
            month = request.args.get("month", type=int)
            week = request.args.get("week", type=int)
            
            # Validate time_range
            if time_range not in ["weekly", "monthly", "yearly"]:
                return jsonify({
                    "error": "time_range must be 'weekly', 'monthly', or 'yearly'"
                }), 400
            
            # Validate required parameters based on time_range
            if time_range == "monthly" and month is None:
                return jsonify({"error": "month parameter required for monthly time_range"}), 400
            
            if time_range == "weekly" and week is None:
                return jsonify({"error": "week parameter required for weekly time_range"}), 400
            
            # Get time-range analytics
            result = AnalyticsService.get_time_range_analytics(
                user_id=user_id,
                time_range=time_range,
                year=year,
                month=month,
                week=week
            )
            
            return jsonify(result), 200
            
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500
    
    else:
        # Old behavior: all-time summary
        total = AnalyticsService.total_spending(user_id)
        monthly = AnalyticsService.monthly_spending(user_id)
        categories = AnalyticsService.category_breakdown(user_id)
        vendors = AnalyticsService.vendor_breakdown(user_id)

        return jsonify({
            "success": True,
            "total_spending": total,
            "monthly_spending": monthly,
            "category_breakdown": categories,
            "vendor_breakdown": vendors
        }), 200
