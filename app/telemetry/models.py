
from sqlalchemy import (
    Date,
    Index,
    Integer,
    UniqueConstraint,
)

from extensions import db


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    start_datetime = db.Column(db.DateTime, nullable=False)
    duration_sec = db.Column(db.Integer, nullable=False)
    distance_km = db.Column(db.Numeric(10, 3), nullable=False)
    avg_speed_kmh = db.Column(db.Numeric(5, 2), nullable=False)
    active_time_sec = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # relationship to user (optional)
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

    __table_args__ = (
        Index('idx_activities_user_id', 'user_id'),
        Index('idx_activities_start_datetime', 'start_datetime'),
    )

class DailyAggregate(db.Model):
    __tablename__ = 'daily_aggregates'
    date = db.Column(Date, primary_key=True)
    total_distance_km = db.Column(db.Numeric(10, 3), nullable=False)
    duration_sec = db.Column(db.Integer, nullable=False)
    avg_speed_kmh = db.Column(db.Numeric(5, 2), nullable=False)
    active_hours = db.Column(db.Numeric(5, 2), nullable=False)  # active_time_sec / 3600

    __table_args__ = (
        Index('idx_daily_aggregates_date', 'date'),
    )

class HourlyDailyAggregate(db.Model):
    __tablename__ = 'hourly_daily_aggregates'
    date = db.Column(Date, primary_key=True)
    hour = db.Column(Integer, primary_key=True)  # 0-23
    hourly_avg_speed = db.Column(db.Numeric(5, 2), nullable=False)
    hourly_distance_km = db.Column(db.Numeric(10, 3), nullable=False)
    duration_sec = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('date', 'hour', name='uix_hourly_daily_date_hour'),
        Index('idx_hourly_daily_aggregates_date', 'date'),
        Index('idx_hourly_daily_aggregates_hour', 'hour'),
    )

class MonthlyAggregate(db.Model):
    __tablename__ = 'monthly_aggregates'
    year = db.Column(Integer, primary_key=True)
    month = db.Column(Integer, primary_key=True)
    daily_avg_speed = db.Column(db.Numeric(5, 2), nullable=False)
    total_distance_km = db.Column(db.Numeric(10, 3), nullable=False)
    total_duration = db.Column(db.Integer, nullable=False)  # seconds? maybe total duration_sec aggregated
    active_hours = db.Column(db.Numeric(5, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint('year', 'month', name='uix_monthly_year_month'),
        Index('idx_monthly_aggregates_year', 'year'),
        Index('idx_monthly_aggregates_month', 'month'),
    )

class YearlyAggregate(db.Model):
    __tablename__ = 'yearly_aggregates'
    year = db.Column(Integer, primary_key=True)
    monthly_avg_speed = db.Column(db.Numeric(5, 2), nullable=False)
    total_distance_km = db.Column(db.Numeric(10, 3), nullable=False)
    total_duration = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        Index('idx_yearly_aggregates_year', 'year'),
    )

class TimeDim(db.Model):
    __tablename__ = 'time_dim'
    date = db.Column(Date, primary_key=True)
    year = db.Column(Integer, nullable=False)
    month = db.Column(Integer, nullable=False)
    day = db.Column(Integer, nullable=False)
    hour = db.Column(Integer, nullable=True)  # optional for hourly granularity
    week_day = db.Column(Integer, nullable=False)  # 0 Monday, 6 Sunday or as per ISO

    __table_args__ = (
        Index('idx_time_dim_date', 'date'),
        Index('idx_time_dim_year_month', 'year', 'month'),
    )
