"""
Reports & Analytics API
=======================
All endpoints are MANAGER/ADMIN only and tenant-scoped.
Uses raw SQLAlchemy aggregate queries — no ORM lazy loading — for performance.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.auth import RoleEnum, User
from app.models.crm import Client
from app.models.properties import Property, PropertyStatus
from app.models.transactions import Sale
from app.models.visits import Visit, VisitStatus
from app.schemas import TopSaleRead
from app.services.metrics import (
    ReportPeriod,
    comparison_window,
    month_keys,
    month_window,
    percentage,
    period_window,
    utc_now,
    visit_metrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


# ─────────────────────────────────────────────────────────
# GUARDS
# ─────────────────────────────────────────────────────────

def require_manager(current_user: User) -> User:
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.MANAGER]:
        raise HTTPException(status_code=403, detail="Acceso restringido a gestores")
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuario sin tenant asignado")
    return current_user


# ─────────────────────────────────────────────────────────
# HELPER: build date range
# ─────────────────────────────────────────────────────────

def _parse_period(period: ReportPeriod):
    return period_window(period)


# ─────────────────────────────────────────────────────────
# 1. EXECUTIVE KPI SUMMARY
# ─────────────────────────────────────────────────────────

@router.get("/kpi-summary")
def kpi_summary(
    period: ReportPeriod = Query("this_year", description="Period filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Top-level KPIs for the executive dashboard card strip.
    Returns current period vs previous period for trend arrows.
    """
    require_manager(current_user)
    tid = current_user.tenant_id

    now = utc_now()
    start, end = period_window(period, now)
    comparison = comparison_window(period, start, end)

    def sales_in_range(s: datetime, e: datetime):
        return db.query(Sale).filter(
            Sale.is_active.is_(True), Sale.tenant_id == tid,
            Sale.sale_date >= s,
            Sale.sale_date < e,
        ).all()

    current_sales = sales_in_range(start, end)
    prev_sales = sales_in_range(*comparison) if comparison else []

    def _pct_change(current: float, previous: float) -> Optional[float]:
        if previous == 0:
            return None
        return round((current - previous) / previous * 100, 1)

    # Sales metrics
    cur_volume = sum(s.sale_price for s in current_sales)
    cur_agency_comm = sum(s.agency_commission for s in current_sales)
    cur_agent_comm = sum(s.agent_commission for s in current_sales)
    cur_total_comm = sum(s.total_commission for s in current_sales)
    cur_count = len(current_sales)

    prev_volume = sum(s.sale_price for s in prev_sales)
    prev_agency_comm = sum(s.agency_commission for s in prev_sales)
    prev_count = len(prev_sales)

    # Current period avg ticket
    avg_ticket = cur_volume / cur_count if cur_count else None
    avg_commission_pct = (cur_total_comm / cur_volume * 100) if cur_volume else None

    # Portfolio counts
    total_props = db.query(Property).filter(Property.tenant_id == tid).count()
    active_props = db.query(Property).filter(
        Property.tenant_id == tid,
        Property.status.notin_([PropertyStatus.VENDIDA, PropertyStatus.RETIRADA]),
    ).count()
    unassigned_props = db.query(Property).filter(
        Property.tenant_id == tid,
        Property.agent_id.is_(None),
        Property.status.notin_([PropertyStatus.VENDIDA, PropertyStatus.RETIRADA]),
    ).count()
    total_clients = db.query(Client).filter(Client.tenant_id == tid).count()
    total_agents = db.query(User).filter(
        User.tenant_id == tid, User.role == RoleEnum.AGENT, User.is_active.is_(True)
    ).count()

    visits = visit_metrics(db, tid, start, end)
    sold_properties_now = db.query(Property).filter(
        Property.tenant_id == tid, Property.status == PropertyStatus.VENDIDA,
    ).count()

    return {
        "period": period,
        "period_start": start.isoformat() if period != "all" else None,
        "timezone": "UTC",
        "snapshot_at": now.isoformat(),
        "comparison_start": comparison[0].isoformat() if comparison else None,
        "comparison_end": comparison[1].isoformat() if comparison else None,
        "period_end": end.isoformat(),
        # Revenue
        "sales_count": cur_count,
        "sales_count_change": _pct_change(cur_count, prev_count),
        "sales_volume": round(cur_volume, 2),
        "sales_volume_change": _pct_change(cur_volume, prev_volume),
        "agency_commission": round(cur_agency_comm, 2),
        "agency_commission_change": _pct_change(cur_agency_comm, prev_agency_comm),
        "agent_commission_total": round(cur_agent_comm, 2),
        "avg_ticket": round(avg_ticket, 2) if avg_ticket is not None else None,
        "avg_commission_pct": round(avg_commission_pct, 2) if avg_commission_pct is not None else None,
        # Portfolio
        "total_properties": total_props,
        "active_properties": active_props,
        "unassigned_properties": unassigned_props,
        "total_clients": total_clients,
        "total_agents": total_agents,
        # Operational
        **visits,
        "sold_properties_now": sold_properties_now,
        "sold_portfolio_share": percentage(sold_properties_now, total_props),
        "visit_to_offer_rate": None,
        "offer_to_close_rate": None,
        "offer_metrics_unavailable_reason": "Todavía no se registran ofertas vinculadas a visitas y cierres.",
    }


# ─────────────────────────────────────────────────────────
# 2. SALES OVER TIME (monthly trend)
# ─────────────────────────────────────────────────────────

@router.get("/sales-by-period")
def sales_by_period(
    months: int = Query(12, ge=1, le=60, description="Number of months to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly aggregation: count, volume, agency commission and agent commission.
    Used for the main revenue trend chart.
    """
    require_manager(current_user)
    tid = current_user.tenant_id

    cutoff, observed_until = month_window(months)

    rows = (
        db.query(
            extract("year", func.timezone("UTC", Sale.sale_date)).label("year"),
            extract("month", func.timezone("UTC", Sale.sale_date)).label("month"),
            func.count(Sale.id).label("count"),
            func.sum(Sale.sale_price).label("volume"),
            func.sum(Sale.total_commission).label("total_commission"),
            func.sum(Sale.agency_commission).label("agency_commission"),
            func.sum(Sale.agent_commission).label("agent_commission"),
        )
        .filter(Sale.is_active.is_(True), Sale.tenant_id == tid, Sale.sale_date >= cutoff, Sale.sale_date < observed_until)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    result = []
    for r in rows:
        label = f"{int(r.year)}-{int(r.month):02d}"
        result.append({
            "period": label,
            "year": int(r.year),
            "month": int(r.month),
            "count": int(r.count),
            "volume": round(float(r.volume or 0), 2),
            "total_commission": round(float(r.total_commission or 0), 2),
            "agency_commission": round(float(r.agency_commission or 0), 2),
            "agent_commission": round(float(r.agent_commission or 0), 2),
        })

    indexed = {item["period"]: item for item in result}
    return [indexed.get(f"{year}-{month:02d}", {
        "period": f"{year}-{month:02d}", "year": year, "month": month, "count": 0,
        "volume": 0, "total_commission": 0, "agency_commission": 0, "agent_commission": 0,
    }) for year, month in month_keys(cutoff, observed_until)]


# ─────────────────────────────────────────────────────────
# 3. AGENT PERFORMANCE
# ─────────────────────────────────────────────────────────

@router.get("/agent-performance")
def agent_performance(
    period: ReportPeriod = Query("this_year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Per-agent breakdown: sales, volume, commissions, active properties,
    observed visits, attendance, visit-to-close cohorts, period rating. Sorted by sales volume desc.

    Agent list is built from:
      - All tenant users who have ANY sale recorded (regardless of role)
      - UNION all active AGENT-role users (even with 0 sales in period)
    This ensures managers/admins who close deals are never excluded.
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    start, end = _parse_period(period)

    # 1. Collect IDs of users who have at least one sale in this tenant (any role, any period)
    seller_ids_rows = (
        db.query(Sale.agent_id)
        .filter(Sale.is_active.is_(True), Sale.tenant_id == tid, Sale.agent_id.isnot(None))
        .distinct()
        .all()
    )
    seller_ids = {row[0] for row in seller_ids_rows}

    # 2. All active AGENT-role users for this tenant
    agent_users = db.query(User).filter(
        User.tenant_id == tid,
        User.role == RoleEnum.AGENT,
        User.is_active.is_(True),
    ).all()
    agent_ids = {u.id for u in agent_users}

    # 3. Union: fetch User objects for all combined IDs
    visit_agent_ids = {row[0] for row in db.query(Visit.agent_id).filter(
        Visit.tenant_id == tid, Visit.scheduled_at >= start, Visit.scheduled_at < end,
        Visit.agent_id.isnot(None),
    ).distinct().all()}
    all_ids = seller_ids | agent_ids | visit_agent_ids

    agents = db.query(User).filter(User.tenant_id == tid, User.id.in_(list(all_ids))).all()

    result = []
    for agent in agents:
        # Sales in period
        agent_sales = db.query(Sale).filter(
            Sale.is_active.is_(True), Sale.tenant_id == tid,
            Sale.agent_id == agent.id,
            Sale.sale_date >= start,
            Sale.sale_date < end,
        ).all()

        # Active properties
        active_props = db.query(Property).filter(
            Property.tenant_id == tid,
            Property.agent_id == agent.id,
            Property.status.notin_([PropertyStatus.VENDIDA, PropertyStatus.RETIRADA]),
        ).count()

        visits = visit_metrics(db, tid, start, end, agent.id)

        sale_count = len(agent_sales)
        volume = sum(s.sale_price for s in agent_sales)
        agent_commission = sum(s.agent_commission for s in agent_sales)
        avg_ticket = volume / sale_count if sale_count else None

        result.append({
            "agent_id": str(agent.id),
            "agent_name": agent.full_name,
            "agent_email": agent.email,
            "commission_rate": agent.commission_rate or 0.0,
            # Sales
            "sales_count": sale_count,
            "sales_volume": round(volume, 2),
            "agent_commission": round(agent_commission, 2),
            "avg_ticket": round(avg_ticket, 2) if avg_ticket is not None else None,
            # Portfolio
            "active_properties": active_props,
            # Visits
            **visits,
        })

    result.sort(key=lambda x: x["sales_volume"], reverse=True)

    # Show unassigned sales (agent_id IS NULL) as a special row so they are never silent
    unassigned_sales = db.query(Sale).filter(
        Sale.is_active.is_(True), Sale.tenant_id == tid,
        Sale.agent_id.is_(None),
        Sale.sale_date >= start,
        Sale.sale_date < end,
    ).all()
    unassigned_visits = visit_metrics(db, tid, start, end, None)
    if unassigned_sales or unassigned_visits["total_visits"]:
        u_volume = sum(s.sale_price for s in unassigned_sales)
        u_comm = sum(s.agent_commission for s in unassigned_sales)
        result.append({
            "agent_id": None,
            "agent_name": "⚠ Sin agente asignado",
            "agent_email": "—",
            "commission_rate": 0.0,
            "sales_count": len(unassigned_sales),
            "sales_volume": round(u_volume, 2),
            "agent_commission": round(u_comm, 2),
            "avg_ticket": round(u_volume / len(unassigned_sales), 2) if unassigned_sales else None,
            "active_properties": 0,
            **unassigned_visits,
        })

    return result


# ─────────────────────────────────────────────────────────
# 4. PIPELINE FUNNEL
# ─────────────────────────────────────────────────────────

@router.get("/pipeline-funnel")
def pipeline_funnel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Property count and total value by pipeline status.
    Returns data ordered by the sales pipeline progression.
    """
    require_manager(current_user)
    tid = current_user.tenant_id

    pipeline_order = [
        PropertyStatus.CAPTADA,
        PropertyStatus.PUBLICADA,
        PropertyStatus.EN_VISITAS,
        PropertyStatus.RESERVADA,
        PropertyStatus.PENDIENTE_NOTARIA,
        PropertyStatus.VENDIDA,
        PropertyStatus.RETIRADA,
    ]

    status_labels = {
        PropertyStatus.CAPTADA: "Captada",
        PropertyStatus.PUBLICADA: "Publicada",
        PropertyStatus.EN_VISITAS: "En Visitas",
        PropertyStatus.RESERVADA: "Reservada",
        PropertyStatus.PENDIENTE_NOTARIA: "Pendiente Notaría",
        PropertyStatus.VENDIDA: "Vendida",
        PropertyStatus.RETIRADA: "Retirada",
    }

    rows = (
        db.query(
            Property.status,
            func.count(Property.id).label("count"),
            func.sum(Property.price).label("total_value"),
            func.avg(Property.price).label("avg_price"),
        )
        .filter(Property.tenant_id == tid)
        .group_by(Property.status)
        .all()
    )

    by_status = {r.status: r for r in rows}

    result = []
    for status in pipeline_order:
        r = by_status.get(status)
        result.append({
            "status": status.value,
            "label": status_labels[status],
            "count": int(r.count) if r else 0,
            "total_value": round(float(r.total_value or 0), 2) if r else 0,
            "avg_price": round(float(r.avg_price or 0), 2) if r else 0,
        })

    return result


# ─────────────────────────────────────────────────────────
# 5. PROPERTY TYPE BREAKDOWN
# ─────────────────────────────────────────────────────────

@router.get("/property-type-breakdown")
def property_type_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Portfolio composition by property type — count and avg price.
    Used for pie/donut chart.
    """
    require_manager(current_user)
    tid = current_user.tenant_id

    rows = (
        db.query(
            Property.property_type,
            func.count(Property.id).label("count"),
            func.sum(Property.price).label("total_value"),
            func.avg(Property.price).label("avg_price"),
        )
        .filter(
            Property.tenant_id == tid,
            Property.status.notin_([PropertyStatus.RETIRADA]),
        )
        .group_by(Property.property_type)
        .order_by(func.count(Property.id).desc())
        .all()
    )

    type_labels = {
        "PISO": "Piso", "CASA": "Casa", "CHALET": "Chalet", "ATICO": "Ático",
        "LOCAL": "Local Comercial", "OFICINA": "Oficina", "TERRENO": "Terreno",
        "GARAJE": "Garaje", "TRASTERO": "Trastero",
    }

    total_count = sum(int(r.count) for r in rows)
    return [
        {
            "type": r.property_type.value if r.property_type else "Otro",
            "label": type_labels.get(r.property_type.value if r.property_type else "", "Otro"),
            "count": int(r.count),
            "percentage": round(int(r.count) / total_count * 100, 1) if total_count else 0,
            "total_value": round(float(r.total_value or 0), 2),
            "avg_price": round(float(r.avg_price or 0), 2),
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────
# 6. COMMISSION SUMMARY
# ─────────────────────────────────────────────────────────

@router.get("/commission-summary")
def commission_summary(
    period: ReportPeriod = Query("this_year"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Quarterly commission breakdown — agency vs agents.
    Used for stacked bar chart.
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    start, end = _parse_period(period)

    rows = (
        db.query(
            extract("year", func.timezone("UTC", Sale.sale_date)).label("year"),
            extract("quarter", func.timezone("UTC", Sale.sale_date)).label("quarter"),
            func.sum(Sale.agency_commission).label("agency"),
            func.sum(Sale.agent_commission).label("agents"),
            func.sum(Sale.total_commission).label("total"),
            func.count(Sale.id).label("sales"),
        )
        .filter(Sale.is_active.is_(True), Sale.tenant_id == tid, Sale.sale_date >= start, Sale.sale_date < end)
        .group_by("year", "quarter")
        .order_by("year", "quarter")
        .all()
    )

    quarter_labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    return [
        {
            "label": f"{int(r.year)} {quarter_labels[int(r.quarter)]}",
            "year": int(r.year),
            "quarter": int(r.quarter),
            "agency_commission": round(float(r.agency or 0), 2),
            "agent_commission": round(float(r.agents or 0), 2),
            "total_commission": round(float(r.total or 0), 2),
            "sales_count": int(r.sales),
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────
# 7. VISIT ANALYTICS
# ─────────────────────────────────────────────────────────

@router.get("/visit-analytics")
def visit_analytics(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly visit counts by status — scheduled, completed, cancelled, no-show.
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    cutoff, observed_until = month_window(months)

    rows = (
        db.query(
            extract("year", func.timezone("UTC", Visit.scheduled_at)).label("year"),
            extract("month", func.timezone("UTC", Visit.scheduled_at)).label("month"),
            Visit.status,
            func.count(Visit.id).label("count"),
        )
        .filter(Visit.tenant_id == tid, Visit.scheduled_at >= cutoff, Visit.scheduled_at < observed_until)
        .group_by("year", "month", Visit.status)
        .order_by("year", "month")
        .all()
    )

    # Pivot by period
    by_period: dict = {}
    for r in rows:
        key = f"{int(r.year)}-{int(r.month):02d}"
        if key not in by_period:
            by_period[key] = {
                "period": key,
                "year": int(r.year),
                "month": int(r.month),
                "SCHEDULED": 0, "COMPLETED": 0, "CANCELLED": 0, "NO_SHOW": 0,
            }
        status_key = r.status.value if r.status else "SCHEDULED"
        by_period[key][status_key] = int(r.count)

    result = []
    for year, month in month_keys(cutoff, observed_until):
        key = f"{year}-{month:02d}"
        item = by_period.get(key, {"period": key, "year": year, "month": month,
            "SCHEDULED": 0, "COMPLETED": 0, "CANCELLED": 0, "NO_SHOW": 0})
        item["total"] = sum(item[state] for state in ("SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"))
        item["attendance_denominator"] = item["COMPLETED"] + item["NO_SHOW"]
        item["visit_attendance_rate"] = percentage(item["COMPLETED"], item["attendance_denominator"])
        result.append(item)
    return result


# ─────────────────────────────────────────────────────────
# 8. CLIENT ACQUISITION
# ─────────────────────────────────────────────────────────

@router.get("/client-acquisition")
def client_acquisition(
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly new clients by type (OWNER vs BUYER).
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    cutoff, observed_until = month_window(months)

    rows = (
        db.query(
            extract("year", func.timezone("UTC", Client.created_at)).label("year"),
            extract("month", func.timezone("UTC", Client.created_at)).label("month"),
            Client.client_type,
            func.count(Client.id).label("count"),
        )
        .filter(Client.tenant_id == tid, Client.created_at >= cutoff, Client.created_at < observed_until)
        .group_by("year", "month", Client.client_type)
        .order_by("year", "month")
        .all()
    )

    by_period: dict = {}
    for r in rows:
        key = f"{int(r.year)}-{int(r.month):02d}"
        if key not in by_period:
            by_period[key] = {"period": key, "Propietario": 0, "Demandante": 0, "total": 0}
        type_key = r.client_type.value if r.client_type else "Propietario"
        by_period[key][type_key] = int(r.count)
        by_period[key]["total"] += int(r.count)

    return [by_period.get(f"{year}-{month:02d}", {
        "period": f"{year}-{month:02d}", "Propietario": 0, "Demandante": 0, "total": 0,
    }) for year, month in month_keys(cutoff, observed_until)]


# ─────────────────────────────────────────────────────────
# 9. TOP PERFORMING PROPERTIES (by sale price)
# ─────────────────────────────────────────────────────────

@router.get("/top-sales", response_model=list[TopSaleRead])
def top_sales(
    period: ReportPeriod = Query("this_year"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Top N sales sorted by sale_price descending.
    Eagerly loads property, agent and buyer to avoid N+1 queries.
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    start, end = _parse_period(period)

    return (
        db.query(Sale)
        .options(
            joinedload(Sale.property),
            joinedload(Sale.agent),
            joinedload(Sale.buyer),
        )
        .filter(Sale.is_active.is_(True), Sale.tenant_id == tid, Sale.sale_date >= start, Sale.sale_date < end)
        .order_by(Sale.sale_price.desc())
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────────────────
# 10. PRICE RANGE DISTRIBUTION
# ─────────────────────────────────────────────────────────

@router.get("/price-distribution")
def price_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bucket properties into price ranges for a histogram.
    """
    require_manager(current_user)
    tid = current_user.tenant_id

    buckets = [
        (0,       100_000,  "< 100K"),
        (100_000, 200_000,  "100K–200K"),
        (200_000, 300_000,  "200K–300K"),
        (300_000, 500_000,  "300K–500K"),
        (500_000, 750_000,  "500K–750K"),
        (750_000, 1_000_000,"750K–1M"),
        (1_000_000, None,   "> 1M"),
    ]

    result = []
    for low, high, label in buckets:
        q = db.query(func.count(Property.id)).filter(
            Property.tenant_id == tid,
            Property.status.notin_([PropertyStatus.RETIRADA]),
            Property.price >= low,
        )
        if high is not None:
            q = q.filter(Property.price < high)
        count = q.scalar() or 0
        result.append({"range": label, "count": int(count), "low": low, "high": high})

    return result


# ─────────────────────────────────────────────────────────
# 11. AGENT EVOLUTION (monthly time-series per agent)
# ─────────────────────────────────────────────────────────

@router.get("/agent-evolution")
def agent_evolution(
    months: int = Query(12, ge=3, le=36, description="How many months back to look"),
    agent_ids: Optional[str] = Query(
        None,
        description="Comma-separated list of agent UUIDs. Empty = all agents with activity."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly evolution per agent for the main KPIs:
      - sales_count, sales_volume, agent_commission
      - visits_total, visits_completed

    Returns one entry per agent with a `monthly` array covering every
    month in the requested window (missing months are filled with zeros).

    Optional agent_ids filter (comma-separated UUIDs) narrows results.
    """
    require_manager(current_user)
    tid = current_user.tenant_id
    cutoff, observed_until = month_window(months)

    all_periods = month_keys(cutoff, observed_until)

    # ── Resolve which agents to include ─────────────────
    import uuid as _uuid

    requested_ids: Optional[list] = None
    if agent_ids and agent_ids.strip():
        try:
            requested_ids = [_uuid.UUID(aid.strip()) for aid in agent_ids.split(",") if aid.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid UUID in agent_ids") from None

    # All users who have at least one sale or visit in the window
    sale_agent_q = (
        db.query(Sale.agent_id)
        .filter(Sale.is_active.is_(True), Sale.tenant_id == tid, Sale.agent_id.isnot(None), Sale.sale_date >= cutoff, Sale.sale_date < observed_until)
        .distinct()
    )
    visit_agent_q = (
        db.query(Visit.agent_id)
        .filter(Visit.tenant_id == tid, Visit.agent_id.isnot(None), Visit.scheduled_at >= cutoff, Visit.scheduled_at < observed_until)
        .distinct()
    )
    active_ids = {r[0] for r in sale_agent_q.all()} | {r[0] for r in visit_agent_q.all()}

    # Also include all active AGENT-role users even with no activity
    roster_ids = {
        u.id
        for u in db.query(User).filter(
            User.tenant_id == tid, User.role == RoleEnum.AGENT, User.is_active.is_(True)
        ).all()
    }
    candidate_ids = active_ids | roster_ids

    if requested_ids:
        candidate_ids = {aid for aid in candidate_ids if aid in requested_ids}

    if not candidate_ids:
        return []

    agents = db.query(User).filter(User.tenant_id == tid, User.id.in_(list(candidate_ids))).all()

    # ── Aggregate sales per (agent, year, month) ────────
    sales_rows = (
        db.query(
            Sale.agent_id,
            extract("year", func.timezone("UTC", Sale.sale_date)).label("yr"),
            extract("month", func.timezone("UTC", Sale.sale_date)).label("mo"),
            func.count(Sale.id).label("cnt"),
            func.sum(Sale.sale_price).label("vol"),
            func.sum(Sale.agent_commission).label("comm"),
        )
        .filter(
            Sale.is_active.is_(True), Sale.tenant_id == tid,
            Sale.agent_id.in_(list(candidate_ids)),
            Sale.sale_date >= cutoff, Sale.sale_date < observed_until,
        )
        .group_by(Sale.agent_id, "yr", "mo")
        .all()
    )

    # ── Aggregate visits per (agent, year, month) ────────
    visits_rows = (
        db.query(
            Visit.agent_id,
            extract("year", func.timezone("UTC", Visit.scheduled_at)).label("yr"),
            extract("month", func.timezone("UTC", Visit.scheduled_at)).label("mo"),
            func.count(Visit.id).label("total"),
            func.sum(
                case((Visit.status == VisitStatus.COMPLETED, 1), else_=0)
            ).label("completed"),
        )
        .filter(
            Visit.tenant_id == tid,
            Visit.agent_id.in_(list(candidate_ids)),
            Visit.scheduled_at >= cutoff, Visit.scheduled_at < observed_until,
        )
        .group_by(Visit.agent_id, "yr", "mo")
        .all()
    )

    # ── Index by (agent_id, year, month) ─────────────────
    sales_idx: dict = {}
    for r in sales_rows:
        sales_idx[(r.agent_id, int(r.yr), int(r.mo))] = {
            "sales_count": int(r.cnt),
            "sales_volume": round(float(r.vol or 0), 2),
            "agent_commission": round(float(r.comm or 0), 2),
        }

    visits_idx: dict = {}
    for r in visits_rows:
        visits_idx[(r.agent_id, int(r.yr), int(r.mo))] = {
            "visits_total": int(r.total),
            "visits_completed": int(r.completed),
        }

    # ── Build output per agent ────────────────────────────
    result = []
    for agent in agents:
        monthly = []
        for yr, mo in all_periods:
            s = sales_idx.get((agent.id, yr, mo), {})
            v = visits_idx.get((agent.id, yr, mo), {})
            monthly.append({
                "period": f"{yr}-{mo:02d}",
                "year": yr,
                "month": mo,
                "sales_count": s.get("sales_count", 0),
                "sales_volume": s.get("sales_volume", 0.0),
                "agent_commission": s.get("agent_commission", 0.0),
                "visits_total": v.get("visits_total", 0),
                "visits_completed": v.get("visits_completed", 0),
            })

        # Properties currently assigned (point-in-time)
        assigned_props = db.query(func.count(Property.id)).filter(
            Property.tenant_id == tid,
            Property.agent_id == agent.id,
            Property.status.notin_([PropertyStatus.VENDIDA, PropertyStatus.RETIRADA]),
        ).scalar() or 0

        result.append({
            "agent_id": str(agent.id),
            "agent_name": agent.full_name,
            "agent_email": agent.email,
            "assigned_properties": int(assigned_props),
            "monthly": monthly,
        })

    # Sort by total recent volume descending
    result.sort(
        key=lambda x: sum(m["sales_volume"] for m in x["monthly"]),
        reverse=True,
    )
    return result
