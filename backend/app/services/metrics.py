"""Report definitions: UTC windows, observed attendance and visit cohorts."""

from datetime import datetime, timezone
from typing import Literal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app.models.transactions import Sale
from app.models.visits import Visit, VisitStatus

ReportPeriod = Literal[
    "this_month",
    "last_month",
    "this_quarter",
    "last_quarter",
    "this_year",
    "last_year",
    "last_12_months",
    "all",
]
ANY_AGENT = object()


def utc_now():
    return datetime.now(timezone.utc)


def period_window(period: ReportPeriod, now=None):
    """Half-open UTC interval; current periods stop at the observation instant."""
    now = now or utc_now()
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    quarter = month.replace(month=((month.month - 1) // 3) * 3 + 1)
    year = month.replace(month=1)
    windows = {
        "this_month": (month, now),
        "last_month": (month - relativedelta(months=1), month),
        "this_quarter": (quarter, now),
        "last_quarter": (quarter - relativedelta(months=3), quarter),
        "this_year": (year, now),
        "last_year": (year - relativedelta(years=1), year),
        "last_12_months": (now - relativedelta(months=12), now),
        "all": (datetime.min.replace(tzinfo=timezone.utc), now),
    }
    return windows[period]


def comparison_window(period: ReportPeriod, start, end):
    """Full prior calendar periods, or the same elapsed duration for partial ones."""
    if period == "all":
        return None
    months = (
        1
        if "month" in period and period != "last_12_months"
        else 3
        if "quarter" in period
        else 12
    )
    previous_start = start - relativedelta(months=months)
    previous_end = (
        min(start, previous_start + (end - start))
        if period.startswith("this_")
        else start
    )
    return previous_start, previous_end


def month_window(months, now=None):
    end = now or utc_now()
    start = end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ) - relativedelta(months=months - 1)
    return start, end


def month_keys(start, end):
    cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    keys = []
    # Include the current calendar month even exactly at its first instant.
    while cursor <= end:
        keys.append((cursor.year, cursor.month))
        cursor += relativedelta(months=1)
    return keys


def percentage(numerator, denominator):
    return round(numerator / denominator * 100, 1) if denominator else None


def visit_metrics(db, tenant_id, start, end, agent_id=ANY_AGENT):
    query = db.query(Visit).filter(
        Visit.tenant_id == tenant_id,
        Visit.scheduled_at >= start,
        Visit.scheduled_at < end,
    )
    if agent_id is not ANY_AGENT:
        query = query.filter(Visit.agent_id == agent_id)
    counts = dict(
        query.with_entities(Visit.status, func.count(Visit.id))
        .group_by(Visit.status)
        .all()
    )
    completed = counts.get(VisitStatus.COMPLETED, 0)
    no_show = counts.get(VisitStatus.NO_SHOW, 0)
    rating, rated = (
        query.filter(Visit.status == VisitStatus.COMPLETED, Visit.rating.isnot(None))
        .with_entities(func.avg(Visit.rating), func.count(Visit.id))
        .one()
    )

    # A buyer/property pair is counted once even if several visits were needed.
    cohort = (
        query.filter(Visit.status == VisitStatus.COMPLETED, Visit.client_id.isnot(None))
        .with_entities(
            Visit.property_id.label("property_id"),
            Visit.client_id.label("buyer_id"),
            func.min(Visit.scheduled_at).label("first_visit"),
        )
        .group_by(Visit.property_id, Visit.client_id)
        .subquery()
    )
    matching_sale = (
        db.query(Sale.id)
        .filter(
            Sale.tenant_id == tenant_id,
            Sale.is_active.is_(True),
            Sale.property_id == cohort.c.property_id,
            Sale.buyer_id == cohort.c.buyer_id,
            Sale.sale_date >= cohort.c.first_visit,
            Sale.sale_date < end,
        )
        .exists()
    )
    eligible, converted = (
        db.query(func.count(), func.count().filter(matching_sale))
        .select_from(cohort)
        .one()
    )
    missing_buyer = query.filter(
        Visit.status == VisitStatus.COMPLETED, Visit.client_id.is_(None)
    ).count()
    return {
        "total_visits": sum(counts.values()),
        "completed_visits": completed,
        "no_show_visits": no_show,
        "cancelled_visits": counts.get(VisitStatus.CANCELLED, 0),
        "unresolved_visits": counts.get(VisitStatus.SCHEDULED, 0),
        "attendance_denominator": completed + no_show,
        "visit_attendance_rate": percentage(completed, completed + no_show),
        "visited_buyer_property_pairs": eligible,
        "closed_buyer_property_pairs": converted,
        "visit_to_close_rate": percentage(converted, eligible),
        "completed_visits_without_buyer": missing_buyer,
        "avg_client_rating": round(float(rating), 2) if rating is not None else None,
        "rated_visits": rated,
    }
