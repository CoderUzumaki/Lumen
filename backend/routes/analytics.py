from flask import Blueprint, request, jsonify
from utils.analytics_service import AnalyticsService

analytics_bp = Blueprint("analytics_bp", __name__)

@analytics_bp.route("/analytics/summary", methods=["GET"])
def analytics_summary():
    """
    Get analytics summary with time-range based filtering
    
    Query Parameters:
    - user_id: string (required)
    - time_range: "weekly" | "monthly" | "yearly" (optional, if provided triggers new behavior)
    - year: number (required if time_range is provided)
    - month: number (optional, 0-11 for monthly time_range)
    - week: number (optional, 1-52 for weekly time_range)
    
    Examples:
    - GET /analytics/summary?user_id=123  (old behavior - all-time summary)
    - GET /analytics/summary?user_id=123&time_range=yearly&year=2025
    - GET /analytics/summary?user_id=123&time_range=monthly&year=2025&month=10
    - GET /analytics/summary?user_id=123&time_range=weekly&year=2025&week=45
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

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
