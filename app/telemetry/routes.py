import logging
from datetime import date, datetime

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import extract, func

from app.telemetry.models import (
    Activity,
    DailyAggregate,
    HourlyDailyAggregate,
    MonthlyAggregate,
    YearlyAggregate,
)
from extensions import db

logger = logging.getLogger(__name__)

telemetry_bp = Blueprint('telemetry', __name__)

def _validate_and_create_activity(data):
    """Validate input and create Activity instance."""
    required = ['start_datetime', 'duration_sec', 'distance_km', 'user_id']
    for field in required:
        if field not in data:
            abort(400, description=f"Missing field: {field}")
    try:
        start_dt = datetime.fromisoformat(data['start_datetime'].replace('Z', '+00:00'))
    except ValueError:
        abort(400, description="Invalid start_datetime format; expected ISO 8601")
    duration_sec = int(data['duration_sec'])
    distance_km = float(data['distance_km'])
    active_time_sec = int(data.get('active_time_sec', duration_sec))  # default to duration if not provided
    if duration_sec <= 0 or distance_km < 0 or active_time_sec < 0 or active_time_sec > duration_sec:
        abort(400, description="Invalid values for duration, distance, or active_time")
    avg_speed_kmh = distance_km / (duration_sec / 3600) if duration_sec > 0 else 0.0
    activity = Activity(
        start_datetime=start_dt,
        duration_sec=duration_sec,
        distance_km=distance_km,
        avg_speed_kmh=round(avg_speed_kmh, 2),
        active_time_sec=active_time_sec,
        user_id=int(data['user_id'])
    )
    return activity

def _update_daily_aggregates(activity_date):
    """Recompute daily aggregates for given date from activities."""
    # Compute aggregates
    result = db.session.query(
        func.sum(Activity.distance_km).label('total_distance_km'),
        func.sum(Activity.duration_sec).label('duration_sec'),
        func.avg(Activity.avg_speed_kmh).label('avg_speed_kmh'),
        func.sum(Activity.active_time_sec).label('active_time_sec')
    ).filter(
        func.date(Activity.start_datetime) == activity_date
    ).one()
    total_distance_km = result.total_distance_km or 0
    duration_sec = result.duration_sec or 0
    avg_speed_kmh = float(result.avg_speed_kmh) if result.avg_speed_kmh is not None else 0.0
    active_time_sec = result.active_time_sec or 0
    active_hours = active_time_sec / 3600.0

    # Upsert daily aggregate
    daily = DailyAggregate.query.get(activity_date)
    if not daily:
        daily = DailyAggregate(date=activity_date)
        db.session.add(daily)
    daily.total_distance_km = round(total_distance_km, 3)
    daily.duration_sec = duration_sec
    daily.avg_speed_kmh = round(avg_speed_kmh, 2)
    daily.active_hours = round(active_hours, 2)
    db.session.flush()

def _update_hourly_daily_aggregates(activity_date):
    """Recompute hourly aggregates for given date from activities."""
    # Delete existing hourly aggregates for this date to replace
    HourlyDailyAggregate.query.filter_by(date=activity_date).delete()
    # Compute per hour
    rows = db.session.query(
        extract('hour', Activity.start_datetime).label('hour'),
        func.sum(Activity.distance_km).label('hourly_distance_km'),
        func.sum(Activity.duration_sec).label('duration_sec'),
        func.avg(Activity.avg_speed_kmh).label('hourly_avg_speed')
    ).filter(
        func.date(Activity.start_datetime) == activity_date
    ).group_by(extract('hour', Activity.start_datetime)).all()
    for row in rows:
        hour = int(row.hour) if row.hour is not None else 0
        hourly_distance_km = row.hourly_distance_km or 0
        duration_sec = row.duration_sec or 0
        hourly_avg_speed = float(row.hourly_avg_speed) if row.hourly_avg_speed is not None else 0.0
        hda = HourlyDailyAggregate(
            date=activity_date,
            hour=hour,
            hourly_distance_km=round(hourly_distance_km, 3),
            duration_sec=duration_sec,
            hourly_avg_speed=round(hourly_avg_speed, 2)
        )
        db.session.add(hda)
    db.session.flush()

def _update_monthly_aggregates(year, month):
    """Recompute monthly aggregates from daily aggregates."""
    # Compute from daily aggregates for given year/month
    result = db.session.query(
        func.avg(DailyAggregate.avg_speed_kmh).label('daily_avg_speed'),
        func.sum(DailyAggregate.total_distance_km).label('total_distance_km'),
        func.sum(DailyAggregate.duration_sec).label('total_duration'),
        func.sum(DailyAggregate.active_hours).label('active_hours')
    ).filter(
        extract('year', DailyAggregate.date) == year,
        extract('month', DailyAggregate.date) == month
    ).one()
    daily_avg_speed = float(result.daily_avg_speed) if result.daily_avg_speed is not None else 0.0
    total_distance_km = result.total_distance_km or 0
    total_duration = result.total_duration or 0
    active_hours = result.active_hours or 0.0

    monthly = MonthlyAggregate.query.filter_by(year=year, month=month).first()
    if not monthly:
        monthly = MonthlyAggregate(year=year, month=month)
        db.session.add(monthly)
    monthly.daily_avg_speed = round(daily_avg_speed, 2)
    monthly.total_distance_km = round(total_distance_km, 3)
    monthly.total_duration = total_duration
    monthly.active_hours = round(active_hours, 2)
    db.session.flush()

def _update_yearly_aggregates(year):
    """Recompute yearly aggregates from monthly aggregates."""
    result = db.session.query(
        func.avg(MonthlyAggregate.daily_avg_speed).label('monthly_avg_speed'),
        func.sum(MonthlyAggregate.total_distance_km).label('total_distance_km'),
        func.sum(MonthlyAggregate.total_duration).label('total_duration')
    ).filter(
        MonthlyAggregate.year == year
    ).one()
    monthly_avg_speed = float(result.monthly_avg_speed) if result.monthly_avg_speed is not None else 0.0
    total_distance_km = result.total_distance_km or 0
    total_duration = result.total_duration or 0

    yearly = YearlyAggregate.query.filter_by(year=year).first()
    if not yearly:
        yearly = YearlyAggregate(year=year)
        db.session.add(yearly)
    yearly.monthly_avg_speed = round(monthly_avg_speed, 2)
    yearly.total_distance_km = round(total_distance_km, 3)
    yearly.total_duration = total_duration
    db.session.flush()

@telemetry_bp.route('/activity', methods=['POST'])
def create_activity():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    data = request.get_json()
    try:
        activity = _validate_and_create_activity(data)
        db.session.add(activity)
        # Flush to get activity.id if needed
        db.session.flush()
        activity_date = activity.start_datetime.date()
        # Update aggregates
        _update_daily_aggregates(activity_date)
        _update_hourly_daily_aggregates(activity_date)
        # Update monthly and yearly aggregates based on activity date
        _update_monthly_aggregates(activity_date.year, activity_date.month)
        _update_yearly_aggregates(activity_date.year)
        db.session.commit()
        return jsonify({"status": "ok", "activity_id": activity.id}), 201
    except Exception:
        db.session.rollback()
        logger.exception("Error creating activity")
        abort(500, description="Internal server error")

@telemetry_bp.route('/data/day', methods=['GET'])
def get_day():
    date_str = request.args.get('date')
    if not date_str:
        abort(400, description="Missing 'date' parameter (YYYY-MM-DD)")
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        abort(400, description="Invalid date format; expected YYYY-MM-DD")
    # Get daily aggregate
    daily = DailyAggregate.query.get(d)
    if not daily:
        abort(404, description="No data for this date")
    # Get hourly array
    hourly = HourlyDailyAggregate.query.filter_by(date=d).order_by(HourlyDailyAggregate.hour).all()
    hourly_list = [{
        "hour": h.hour,
        "avg_speed_kmh": float(h.hourly_avg_speed),
        "distance_km": float(h.hourly_distance_km),
        "duration_sec": h.duration_sec
    } for h in hourly]
    # Get raw activities for the day (optional)
    activities = Activity.query.filter(func.date(Activity.start_datetime) == d).all()
    activity_list = [{
        "id": a.id,
        "start_datetime": a.start_datetime.isoformat(),
        "duration_sec": a.duration_sec,
        "distance_km": float(a.distance_km),
        "avg_speed_kmh": float(a.avg_speed_kmh),
        "active_time_sec": a.active_time_sec,
        "user_id": a.user_id
    } for a in activities]
    return jsonify({
        "date": d.isoformat(),
        "daily": {
            "total_distance_km": float(daily.total_distance_km),
            "duration_sec": daily.duration_sec,
            "avg_speed_kmh": float(daily.avg_speed_kmh),
            "active_hours": float(daily.active_hours)
        },
        "hourly": hourly_list,
        "activities": activity_list
    })

@telemetry_bp.route('/data/day-hour', methods=['GET'])
def get_day_hour():
    date_str = request.args.get('date')
    if not date_str:
        abort(400, description="Missing 'date' parameter")
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        abort(400, description="Invalid date format")
    hourly = HourlyDailyAggregate.query.filter_by(date=d).order_by(HourlyDailyAggregate.hour).all()
    if not hourly:
        abort(404, description="No hourly data for this date")
    hourly_list = [{
        "hour": h.hour,
        "avg_speed_kmh": float(h.hourly_avg_speed),
        "distance_km": float(h.hourly_distance_km),
        "duration_sec": h.duration_sec
    } for h in hourly]
    return jsonify({
        "date": d.isoformat(),
        "hourly": hourly_list
    })

@telemetry_bp.route('/data/week-hour', methods=['GET'])
def get_week_hourly():
    start_str = request.args.get('start')
    if not start_str:
        abort(400, description="Missing 'start' parameter (start date YYYY-MM-DD)")
    try:
        start_date = date.fromisoformat(start_str)
    except ValueError:
        abort(400, description="Invalid date format")
    from datetime import timedelta
    end_date = start_date + timedelta(days=6)
    # We'll get daily aggregates for 7 days
    dates = [start_date + timedelta(days=i) for i in range(7)]
    # Build list of daily data with hourly
    result = []
    for d in dates:
        daily = DailyAggregate.query.get(d)
        if not daily:
            # still include day with zero values?
            daily_vals = {"total_distance_km": 0.0, "duration_sec": 0, "avg_speed_kmh": 0.0, "active_hours": 0.0}
        else:
            daily_vals = {
                "total_distance_km": float(daily.total_distance_km),
                "duration_sec": daily.duration_sec,
                "avg_speed_kmh": float(daily.avg_speed_kmh),
                "active_hours": float(daily.active_hours)
            }
        hourly = HourlyDailyAggregate.query.filter_by(date=d).order_by(HourlyDailyAggregate.hour).all()
        hourly_list = [{
            "hour": h.hour,
            "avg_speed_kmh": float(h.hourly_avg_speed),
            "distance_km": float(h.hourly_distance_km),
            "duration_sec": h.duration_sec
        } for h in hourly]
        result.append({
            "date": d.isoformat(),
            "daily": daily_vals,
            "hourly": hourly_list
        })
    # Compute weekly averages
    total_distance = sum(item["daily"]["total_distance_km"] for item in result)
    total_duration = sum(item["daily"]["duration_sec"] for item in result)
    avg_speed = None
    total_active_hours = sum(item["daily"]["active_hours"] for item in result)
    if total_duration > 0:
        # weighted average speed? we can compute total distance / (total duration/3600)
        avg_speed = total_distance / (total_duration / 3600) if total_duration > 0 else 0.0
    weekly_summary = {
        "total_distance_km": total_distance,
        "total_duration_sec": total_duration,
        "avg_speed_kmh": avg_speed,
        "total_active_hours": total_active_hours
    }
    return jsonify({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "weekly_summary": weekly_summary,
        "days": result
    })

@telemetry_bp.route('/data/month', methods=['GET'])
def get_month():
    year = request.args.get('year')
    month = request.args.get('month')
    if not year or not month:
        abort(400, description="Missing 'year' or 'month' parameters")
    try:
        y = int(year)
        m = int(month)
    except ValueError:
        abort(400, description="Year and month must be integers")
    monthly = MonthlyAggregate.query.filter_by(year=y, month=m).first()
    if not monthly:
        abort(404, description="No monthly data for this year/month")
    # Optionally get daily aggregates for the month
    from datetime import date
    start_date = date(y, m, 1)
    # compute end date
    if m == 12:
        end_date = date(y+1, 1, 1)
    else:
        end_date = date(y, m+1, 1)
    # query daily aggregates between start_date and end_date exclusive
    daily_list = DailyAggregate.query.filter(
        DailyAggregate.date >= start_date,
        DailyAggregate.date < end_date
    ).order_by(DailyAggregate.date).all()
    daily_series = [{
        "date": d.date.isoformat(),
        "total_distance_km": float(d.total_distance_km),
        "duration_sec": d.duration_sec,
        "avg_speed_kmh": float(d.avg_speed_kmh),
        "active_hours": float(d.active_hours)
    } for d in daily_list]
    return jsonify({
        "year": y,
        "month": m,
        "monthly": {
            "daily_avg_speed": float(monthly.daily_avg_speed),
            "total_distance_km": float(monthly.total_distance_km),
            "total_duration": monthly.total_duration,
            "active_hours": float(monthly.active_hours)
        },
        "daily_series": daily_series
    })

@telemetry_bp.route('/data/year', methods=['GET'])
def get_year():
    year = request.args.get('year')
    if not year:
        abort(400, description="Missing 'year' parameter")
    try:
        y = int(year)
    except ValueError:
        abort(400, description="Year must be integer")
    yearly = YearlyAggregate.query.filter_by(year=y).first()
    if not yearly:
        abort(404, description="No yearly data for this year")
    # Optionally get monthly aggregates for the year
    monthly_list = MonthlyAggregate.query.filter_by(year=y).order_by(MonthlyAggregate.month).all()
    monthly_series = [{
        "month": m.month,
        "daily_avg_speed": float(m.daily_avg_speed),
        "total_distance_km": float(m.total_distance_km),
        "total_duration": m.total_duration,
        "active_hours": float(m.active_hours)
    } for m in monthly_list]
    return jsonify({
        "year": y,
        "yearly": {
            "monthly_avg_speed": float(yearly.monthly_avg_speed),
            "total_distance_km": float(yearly.total_distance_km),
            "total_duration": yearly.total_duration
        },
        "monthly_series": monthly_series
    })
