from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.annual_summary import AnnualSummary
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.transaction import Transaction
from app.models.instrument import Instrument
from datetime import date

router = APIRouter(prefix="/api/annual", tags=["annual"])


@router.get("")
def get_annual_growth(db: Session = Depends(get_db)):
    summaries = db.query(AnnualSummary).order_by(AnnualSummary.year.asc()).all()

    dec_snapshots = (
        db.query(PortfolioSnapshot)
        .filter(func.strftime("%m", PortfolioSnapshot.date) == "12")
        .all()
    )
    end_by_year: dict[int, float] = {s.date.year: (s.total_brl or 0) for s in dec_snapshots}

    current_year = date.today().year
    if current_year not in end_by_year:
        latest = (
            db.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.date.desc())
            .first()
        )
        if latest:
            end_by_year[current_year] = latest.total_brl or 0

    items = []
    for s in summaries:
        year = s.year
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        txns = (
            db.query(Transaction)
            .filter(
                Transaction.date >= year_start,
                Transaction.date <= year_end,
                Transaction.type.in_(["aplicacion", "rescate"]),
                Transaction.amount_brl.isnot(None),
            )
            .all()
        )
        txn_net_flow = sum(
            t.amount_brl if t.type == "aplicacion" else -t.amount_brl
            for t in txns
        )

        if txn_net_flow != 0:
            patrimonio_inicio = end_by_year.get(year - 1) or s.total
            patrimonio_fin = end_by_year.get(year)
            net_flow = txn_net_flow
            gain = (
                (patrimonio_fin - patrimonio_inicio - net_flow)
                if (patrimonio_fin is not None and patrimonio_inicio is not None)
                else None
            )
            data_source = "calculated"
        else:
            net_flow = s.net_flow
            gain = s.gain
            patrimonio_inicio = s.total
            patrimonio_fin_snap = end_by_year.get(year)
            if patrimonio_fin_snap is not None:
                patrimonio_fin = patrimonio_fin_snap
            elif patrimonio_inicio is not None:
                patrimonio_fin = (patrimonio_inicio or 0) + (net_flow or 0) + (gain or 0)
            else:
                patrimonio_fin = None
            data_source = "legacy"

        diff = (
            (patrimonio_fin - patrimonio_inicio)
            if (patrimonio_fin is not None and patrimonio_inicio is not None)
            else None
        )
        pct_growth = (
            (diff / patrimonio_inicio)
            if (diff is not None and patrimonio_inicio and patrimonio_inicio != 0)
            else None
        )
        pct_valorization = (
            (gain / diff)
            if (gain is not None and diff is not None and diff != 0)
            else None
        )

        items.append({
            "year": year,
            "patrimonio_inicio": patrimonio_inicio,
            "patrimonio_fin": patrimonio_fin,
            "net_flow": net_flow,
            "gain": gain,
            "diff": diff,
            "pct_growth": pct_growth,
            "pct_valorization": pct_valorization,
            "data_source": data_source,
        })

    total_invested = sum((i["net_flow"] or 0) for i in items)
    total_gained = sum((i["gain"] or 0) for i in items)
    gain_ratio = (total_gained / total_invested) if total_invested != 0 else None

    cagr = None
    valid = [i for i in items if i["patrimonio_inicio"] and i["patrimonio_fin"]]
    if len(valid) >= 2:
        first_item = valid[0]
        last_item = valid[-1]
        n_years = last_item["year"] - first_item["year"]
        if n_years > 0 and first_item["patrimonio_inicio"] > 0:
            cagr = (last_item["patrimonio_fin"] / first_item["patrimonio_inicio"]) ** (1 / n_years) - 1

    return {
        "items": items,
        "metrics": {
            "total_invested": total_invested,
            "total_gained": total_gained,
            "gain_ratio": gain_ratio,
            "cagr": cagr,
        },
    }


@router.get("/monthly")
def get_monthly_growth(year: int = Query(...), db: Session = Depends(get_db)):
    months_result = []
    for month in range(1, 13):
        target_date = date(year, month, 1)
        snapshot = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.date == target_date)
            .first()
        )
        months_result.append({
            "month": month,
            "patrimonio": snapshot.total_brl if snapshot else None,
        })

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.date >= year_start,
            Transaction.date <= year_end,
            Transaction.type.in_(["aplicacion", "rescate"]),
            Transaction.amount_brl.isnot(None),
        )
        .order_by(Transaction.date)
        .all()
    )

    net_flow_by_month: dict[int, float] = {}
    for t in txns:
        m = t.date.month
        amt = t.amount_brl if t.type == "aplicacion" else -t.amount_brl
        net_flow_by_month[m] = net_flow_by_month.get(m, 0) + amt

    dec_prev = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.date == date(year - 1, 12, 1))
        .first()
    )
    if dec_prev:
        base = dec_prev.total_brl or 0
    else:
        first_snap = (
            db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.date >= year_start,
                PortfolioSnapshot.date <= year_end,
            )
            .order_by(PortfolioSnapshot.date.asc())
            .first()
        )
        base = (first_snap.total_brl or 0) if first_snap else 0

    cumulative_nf = 0.0
    for m_data in months_result:
        month = m_data["month"]
        nf = net_flow_by_month.get(month, 0)
        cumulative_nf += nf
        patrimonio = m_data["patrimonio"]
        m_data["net_flow"] = nf
        m_data["valorizacion_acum"] = (
            (patrimonio - base - cumulative_nf) if patrimonio is not None else None
        )

    instrument_ids = {t.instrument_id for t in txns}
    instruments_map: dict[int, str] = {}
    if instrument_ids:
        for inst in db.query(Instrument).filter(Instrument.id.in_(instrument_ids)).all():
            instruments_map[inst.id] = inst.name

    txn_list = [
        {
            "date": str(t.date),
            "month": t.date.month,
            "type": t.type,
            "amount_brl": t.amount_brl,
            "instrument_name": instruments_map.get(t.instrument_id, "Desconocido"),
        }
        for t in txns
    ]

    patrimonio_inicio = base
    dec_snap = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.date == date(year, 12, 1))
        .first()
    )
    if dec_snap:
        patrimonio_fin: float | None = dec_snap.total_brl
    else:
        patrimonio_fin = next(
            (m["patrimonio"] for m in reversed(months_result) if m["patrimonio"] is not None),
            None,
        )

    net_flow_total = sum(net_flow_by_month.values())
    gain_total = (
        (patrimonio_fin - patrimonio_inicio - net_flow_total)
        if patrimonio_fin is not None
        else None
    )
    diff = (patrimonio_fin - patrimonio_inicio) if patrimonio_fin is not None else None
    pct_net_flow = (net_flow_total / diff) if diff else None
    pct_gain = (gain_total / diff) if (diff and gain_total is not None) else None

    return {
        "year": year,
        "months": months_result,
        "transactions": txn_list,
        "summary": {
            "patrimonio_inicio": patrimonio_inicio,
            "patrimonio_fin": patrimonio_fin,
            "net_flow_total": net_flow_total,
            "gain_total": gain_total,
            "pct_net_flow": pct_net_flow,
            "pct_gain": pct_gain,
        },
    }
