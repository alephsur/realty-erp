"""Metric definitions and period boundaries against disposable PostgreSQL."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.usefixtures("sale_env")
NOW = datetime(2026, 3, 15, 12, tzinfo=timezone.utc)


def dt(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "period,start,end",
    [
        ("this_month", "2026-03-01", "2026-03-15T12:00"),
        ("last_month", "2026-02-01", "2026-03-01"),
        ("this_quarter", "2026-01-01", "2026-03-15T12:00"),
        ("last_quarter", "2025-10-01", "2026-01-01"),
        ("this_year", "2026-01-01", "2026-03-15T12:00"),
        ("last_year", "2025-01-01", "2026-01-01"),
        ("last_12_months", "2025-03-15T12:00", "2026-03-15T12:00"),
        ("all", "0001-01-01", "2026-03-15T12:00"),
    ],
)
def test_named_windows_are_explicit_and_utc(period, start, end):
    from app.services.metrics import period_window

    assert period_window(period, NOW) == (dt(start), dt(end))


def test_comparisons_and_calendar_months():
    from app.services.metrics import (
        comparison_window,
        month_keys,
        month_window,
        period_window,
    )

    start, end = period_window("this_month", NOW)
    assert comparison_window("this_month", start, end) == (
        dt("2026-02-01"),
        dt("2026-02-15T12:00"),
    )
    start, end = period_window("last_month", NOW)
    assert comparison_window("last_month", start, end) == (
        dt("2026-01-01"),
        dt("2026-02-01"),
    )
    start, end = period_window("this_month", dt("2024-03-31T18:00"))
    assert comparison_window("this_month", start, end) == (
        dt("2024-02-01"),
        dt("2024-03-01"),
    )
    assert comparison_window("all", start, end) is None
    assert month_keys(*month_window(3, NOW)) == [(2026, 1), (2026, 2), (2026, 3)]
    assert month_keys(*month_window(1, dt("2026-03-01"))) == [(2026, 3)]


@pytest.fixture
def metrics_data(data, monkeypatch):
    from app.api import properties, reports
    from app.services import metrics

    monkeypatch.setattr(metrics, "utc_now", lambda: NOW)
    monkeypatch.setattr(reports, "utc_now", lambda: NOW)
    monkeypatch.setattr(properties, "utc_now", lambda: NOW)
    return data


def visit(
    data,
    when,
    status="COMPLETED",
    *,
    client="buyer",
    agent="agent",
    rating=None,
    prop=None,
    tenant=None,
):
    from app.models.visits import Visit, VisitStatus

    with data.env.sessions() as db:
        row = Visit(
            tenant_id=tenant or data.tenant,
            property_id=prop or data.property,
            client_id=getattr(data, client) if client else None,
            agent_id=getattr(data, agent) if agent else None,
            scheduled_at=dt(when),
            status=VisitStatus(status),
            rating=rating,
        )
        db.add(row)
        db.commit()
        return row.id


def sale(
    data,
    when,
    *,
    price=100000,
    buyer="buyer",
    agent="agent",
    prop=None,
    active=True,
    tenant=None,
):
    from app.models.properties import Property
    from app.models.transactions import Sale

    with data.env.sessions() as db:
        if prop is None:
            prop = uuid4()
            db.add(
                Property(
                    id=prop,
                    tenant_id=tenant or data.tenant,
                    agent_id=getattr(data, agent) if agent else None,
                    title="Metric property",
                    price=price,
                    address="Example address",
                    created_at=dt("2025-01-01"),
                )
            )
            db.flush()
        row = Sale(
            tenant_id=tenant or data.tenant,
            property_id=prop,
            buyer_id=getattr(data, buyer),
            agent_id=getattr(data, agent) if agent else None,
            sale_price=price,
            total_commission=3000,
            agent_commission=1200,
            agency_commission=1800,
            sale_date=dt(when),
            is_active=active,
        )
        db.add(row)
        db.commit()
        return row.id


def test_attendance_excludes_cancelled_unresolved_and_future(metrics_data):
    data = metrics_data
    visit(data, "2026-03-01", rating=5)
    visit(data, "2026-03-02", rating=3)
    visit(data, "2026-03-03", "NO_SHOW", rating=1)
    visit(data, "2026-03-04", "CANCELLED")
    visit(data, "2026-03-05", "SCHEDULED")
    visit(data, "2026-03-20", "SCHEDULED")
    visit(data, "2026-02-20", rating=1)
    client = data.client()
    kpi = client.get("/reports/kpi-summary?period=this_month").json()
    assert kpi["total_visits"] == 5 and kpi["completed_visits"] == 2
    assert kpi["visit_attendance_rate"] == 66.7 and kpi["attendance_denominator"] == 3
    assert kpi["unresolved_visits"] == 1 and kpi["cancelled_visits"] == 1
    assert kpi["avg_client_rating"] == 4 and kpi["rated_visits"] == 2
    agent = next(
        a
        for a in client.get("/reports/agent-performance?period=this_month").json()
        if a["agent_id"] == str(data.agent)
    )
    for key in (
        "visit_attendance_rate",
        "avg_client_rating",
        "total_visits",
        "attendance_denominator",
    ):
        assert agent[key] == kpi[key]
    monthly = client.get("/reports/visit-analytics?months=3").json()
    assert [m["period"] for m in monthly] == ["2026-01", "2026-02", "2026-03"]
    assert monthly[-1]["visit_attendance_rate"] == kpi["visit_attendance_rate"]
    assert monthly[0]["visit_attendance_rate"] is None


def test_no_observations_and_missing_offer_tracking_are_not_zero(metrics_data):
    data = metrics_data
    kpi = data.client().get("/reports/kpi-summary?period=this_month").json()
    for name in (
        "visit_attendance_rate",
        "visit_to_close_rate",
        "visit_to_offer_rate",
        "offer_to_close_rate",
        "avg_ticket",
        "avg_commission_pct",
    ):
        assert kpi[name] is None
    assert "ofertas" in kpi["offer_metrics_unavailable_reason"]
    assert "visit_completion_rate" not in kpi and "portfolio_conversion_rate" not in kpi
    visit(data, "2026-03-01", "NO_SHOW")
    kpi = data.client().get("/reports/kpi-summary?period=this_month").json()
    assert kpi["visit_attendance_rate"] == 0


def test_conversion_matches_buyer_property_and_time_without_duplicate_visits(
    metrics_data,
):
    data = metrics_data
    visit(data, "2026-03-02")
    visit(data, "2026-03-03")
    visit(data, "2026-03-04", client="colleague_buyer")
    visit(data, "2026-03-04", client=None)
    sale(data, "2026-03-06", prop=data.property)
    # Unrelated sales must not inflate the visit cohort result.
    sale(data, "2026-03-07")
    sale(data, "2026-02-20", prop=data.property, buyer="colleague_buyer")
    sale(data, "2026-03-20", prop=data.property, buyer="colleague_buyer")
    sale(data, "2026-03-07", prop=data.property, buyer="colleague_buyer", active=False)
    client = data.client()
    kpi = client.get("/reports/kpi-summary?period=this_month").json()
    assert kpi["visited_buyer_property_pairs"] == 2
    assert kpi["closed_buyer_property_pairs"] == 1 and kpi["visit_to_close_rate"] == 50
    assert kpi["completed_visits_without_buyer"] == 1
    assert kpi["sales_count"] == 2


def test_reopening_removes_conversion_and_correction_changes_period(metrics_data):
    from app.models.transactions import Sale

    data = metrics_data
    visit(data, "2026-03-01")
    sid = sale(data, "2026-03-03", prop=data.property)
    url = "/reports/kpi-summary?period=this_month"
    assert data.client().get(url).json()["visit_to_close_rate"] == 100
    with data.env.sessions() as db:
        db.get(Sale, sid).is_active = False
        db.commit()
    assert data.client().get(url).json()["visit_to_close_rate"] == 0
    with data.env.sessions() as db:
        row = db.get(Sale, sid)
        row.is_active = True
        row.sale_date = dt("2026-04-01")
        db.commit()
    assert data.client().get(url).json()["sales_count"] == 0


def test_period_limits_old_history_future_sales_and_comparisons(metrics_data):
    data = metrics_data
    sale(data, "1999-12-31")
    sale(data, "2026-02-01")
    sale(data, "2026-02-15T12:00")  # Outside the equal elapsed comparison.
    sale(data, "2026-03-01")
    sale(data, "2026-03-15T11:59:59")
    sale(data, "2026-03-15T12:00")
    sale(data, "2026-03-31")
    client = data.client()
    kpi = client.get("/reports/kpi-summary?period=this_month").json()
    assert kpi["sales_count"] == 2 and kpi["sales_count_change"] == 100
    assert kpi["comparison_start"] == "2026-02-01T00:00:00+00:00"
    assert kpi["comparison_end"] == "2026-02-15T12:00:00+00:00"
    assert (
        client.get("/reports/kpi-summary?period=last_month").json()["sales_count"] == 2
    )
    historic = client.get("/reports/kpi-summary?period=all").json()
    assert historic["sales_count"] == 5 and historic["period_start"] is None
    assert (
        historic["comparison_start"] is None and historic["sales_count_change"] is None
    )
    assert len(client.get("/reports/top-sales?period=this_month").json()) == 2
    assert (
        sum(
            x["sales_count"]
            for x in client.get("/reports/commission-summary?period=this_month").json()
        )
        == 2
    )
    for path in ("kpi-summary", "agent-performance", "commission-summary", "top-sales"):
        assert client.get(f"/reports/{path}?period=typo").status_code == 422


def test_monthly_windows_fill_gaps_and_group_in_utc(metrics_data):
    data = metrics_data
    sale(data, "2026-01-01T00:15")
    sale(data, "2026-03-01")
    sale(data, "2026-04-01")
    # Explicitly test a different session timezone: grouping still follows UTC.
    from app.api.reports import sales_by_period
    from app.models.auth import User

    with data.env.sessions() as db:
        db.execute(text("SET LOCAL TIME ZONE 'America/Los_Angeles'"))
        rows = sales_by_period(months=3, db=db, current_user=db.get(User, data.manager))
        assert [r["count"] for r in rows] == [1, 0, 1]
    client = data.client()
    for path in ("sales-by-period", "visit-analytics", "client-acquisition"):
        rows = client.get(f"/reports/{path}?months=3").json()
        assert [r["period"] for r in rows] == ["2026-01", "2026-02", "2026-03"]
    evolution = client.get("/reports/agent-evolution?months=3").json()
    agent = next(a for a in evolution if a["agent_id"] == str(data.agent))
    assert [m["sales_count"] for m in agent["monthly"]] == [1, 0, 1]


def test_tenant_and_agent_attribution_and_unassigned_visits(metrics_data):
    data = metrics_data
    visit(data, "2026-03-01", agent="manager")
    visit(data, "2026-03-02", "NO_SHOW", agent="colleague")
    visit(data, "2026-03-03", agent=None)
    sale(data, "2026-03-04", prop=data.property, agent="colleague")
    sale(
        data,
        "2026-03-05",
        tenant=data.other_tenant,
        buyer="other_buyer",
        agent="outsider",
    )
    client = data.client()
    assert (
        client.get("/reports/kpi-summary?period=this_month").json()["sales_count"] == 1
    )
    assert data.client("agent").get("/reports/kpi-summary").status_code == 403
    rows = client.get("/reports/agent-performance?period=this_month").json()
    manager = next(a for a in rows if a["agent_id"] == str(data.manager))
    colleague = next(a for a in rows if a["agent_id"] == str(data.colleague))
    assert manager["sales_count"] == 0 and manager["visit_to_close_rate"] == 100
    assert colleague["sales_count"] == 1 and colleague["visit_attendance_rate"] == 0
    assert next(a for a in rows if a["agent_id"] is None)["completed_visits"] == 1
    assert all(a["agent_id"] != str(data.outsider) for a in rows)


def test_dashboard_totals_are_earned_to_date_not_future_closings(metrics_data):
    data = metrics_data
    sale(data, "2025-01-01")
    sale(data, "2026-03-20")
    sale(data, "2026-03-02", active=False)
    client = data.client()
    summary = client.get("/properties/stats/summary").json()
    assert summary["total_sales"] == 1 and summary["total_revenue"] == 3000
    agent_summary = data.client("agent").get("/properties/stats/agent-summary").json()
    assert (
        agent_summary["total_sales"] == 1 and agent_summary["total_commission"] == 1200
    )
    agent_rank = next(
        row
        for row in client.get("/properties/stats/agent-ranking").json()
        if row["id"] == str(data.agent)
    )
    assert agent_rank["total_sales"] == 1
