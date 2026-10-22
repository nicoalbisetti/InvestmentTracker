# Equity Trades USD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir registrar operaciones de renta variable en instrumentos USD, ingresando precio en USD y calculando `amount_brl` con la cotización mensual de la tabla `quotes`.

**Architecture:** Se agrega la columna `usd_rate` a `equity_trades` (rate USD/BRL al momento del trade). El campo `price` almacena el precio en moneda nativa del instrumento. El router detecta si el instrumento es USD, auto-resuelve el rate desde `quotes`, y calcula `amount_brl = qty * price * usd_rate`. El servicio de recálculo `equity_recalculate.py` usa la moneda del instrumento para mantener `avg_price` en USD y convertir `balance_brl` y `net_trade_flow` correctamente. El frontend muestra campos USD/BRL en paralelo cuando el instrumento seleccionado es USD.

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite, React 18, TypeScript, Axios, Tailwind CSS, Bun

---

## File Map

| Archivo | Acción |
|---|---|
| `backend/app/database.py` | Modificar — agregar `_migrate_equity_trades_usd(eng)` |
| `backend/app/main.py` | Modificar — llamar migración en `startup()` |
| `backend/app/models/equity_trade.py` | Modificar — agregar columna `usd_rate` |
| `backend/app/schemas/equity_trade.py` | Modificar — agregar `usd_rate` a schemas, `currency`/`is_usd`/`usd_rate_last` a summary |
| `backend/app/routers/equity_trades.py` | Modificar — `_resolve_usd_rate`, `_trade_to_out`, POST, PUT, summary |
| `backend/app/services/equity_recalculate.py` | Modificar — `_get_monthly_rate`, lógica USD en balance y gain |
| `frontend/src/api/equityTrades.ts` | Modificar — agregar `usd_rate`, `instrument_currency`, `currency`, `is_usd`, `usd_rate_last` |
| `frontend/src/components/EquityTradeForm.tsx` | Modificar — detección USD, fetch rate, display dual |
| `frontend/src/pages/EquityTrades.tsx` | Modificar — columna precio con prefijo USD, columna monto USD |
| `frontend/src/components/EquityTradeSummaryCard.tsx` | Modificar — precios con sufijo USD, P&L en USD+BRL |

---

## Task 1: Migración de Schema

**Files:**
- Modify: `backend/app/database.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Agregar función de migración en `database.py`**

Al final de `backend/app/database.py`, antes del último `\n`, agregar:

```python
def _migrate_equity_trades_usd(eng):
    """Add usd_rate column to equity_trades if it doesn't exist."""
    from sqlalchemy import text
    with eng.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(equity_trades)"))]
        if "usd_rate" not in cols:
            conn.execute(text("ALTER TABLE equity_trades ADD COLUMN usd_rate REAL"))
            conn.commit()
```

- [ ] **Step 2: Llamar la migración en `startup()` de `main.py`**

En `backend/app/main.py`, en la función `startup()`, cambiar:

```python
@app.on_event("startup")
def startup():
    from app.database import engine as main_engine, demo_engine, _migrate_provento_items, _migrate_return_source, _migrate_portfolio_snapshot_pk
    _migrate_provento_items(main_engine)
    _migrate_provento_items(demo_engine)
    _migrate_return_source(main_engine)
    _migrate_return_source(demo_engine)
    _migrate_portfolio_snapshot_pk(main_engine)
    _migrate_portfolio_snapshot_pk(demo_engine)
```

Por:

```python
@app.on_event("startup")
def startup():
    from app.database import (
        engine as main_engine, demo_engine,
        _migrate_provento_items, _migrate_return_source,
        _migrate_portfolio_snapshot_pk, _migrate_equity_trades_usd,
    )
    _migrate_provento_items(main_engine)
    _migrate_provento_items(demo_engine)
    _migrate_return_source(main_engine)
    _migrate_return_source(demo_engine)
    _migrate_portfolio_snapshot_pk(main_engine)
    _migrate_portfolio_snapshot_pk(demo_engine)
    _migrate_equity_trades_usd(main_engine)
    _migrate_equity_trades_usd(demo_engine)
```

- [ ] **Step 3: Verificar que la migración corre sin errores**

```bash
cd backend && python3 -c "
from app.database import engine, _migrate_equity_trades_usd
_migrate_equity_trades_usd(engine)
from sqlalchemy import text
with engine.connect() as c:
    cols = [r[1] for r in c.execute(text('PRAGMA table_info(equity_trades)'))]
    print('usd_rate present:', 'usd_rate' in cols)
"
```

Esperado: `usd_rate present: True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/database.py backend/app/main.py
git commit -m "feat(equity-trades): add usd_rate column migration"
```

---

## Task 2: Model y Schemas

**Files:**
- Modify: `backend/app/models/equity_trade.py`
- Modify: `backend/app/schemas/equity_trade.py`

- [ ] **Step 1: Agregar `usd_rate` al modelo SQLAlchemy**

En `backend/app/models/equity_trade.py`, agregar la línea después de `amount_brl`:

```python
    amount_brl = Column(Float, nullable=True)
    usd_rate = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
```

- [ ] **Step 2: Actualizar schemas Pydantic**

Reemplazar el contenido completo de `backend/app/schemas/equity_trade.py`:

```python
from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import date, datetime


class EquityTradeCreate(BaseModel):
    instrument_id: int
    date: date
    trade_type: Literal["compra", "venta"]
    quantity: float
    price: float
    usd_rate: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("quantity", "price")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Debe ser mayor a 0")
        return v


class EquityTradeUpdate(BaseModel):
    date: Optional[date] = None
    trade_type: Optional[Literal["compra", "venta"]] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    usd_rate: Optional[float] = None
    notes: Optional[str] = None


class EquityTradeOut(BaseModel):
    id: int
    instrument_id: int
    date: date
    trade_type: str
    quantity: float
    price: float
    usd_rate: Optional[float]
    amount_brl: Optional[float]
    notes: Optional[str]
    created_at: datetime
    instrument_name: str
    instrument_ticker: Optional[str]
    instrument_currency: str

    model_config = {"from_attributes": True}


class EquityTradeSummary(BaseModel):
    instrument_id: int
    instrument_name: str
    instrument_ticker: Optional[str]
    currency: str
    is_usd: bool
    total_compras_qty: float
    total_ventas_qty: float
    qty_actual: float
    avg_price_compra: Optional[float]
    ultimo_precio: Optional[float]
    usd_rate_last: Optional[float]
    pl_no_realizado: Optional[float]
    pl_no_realizado_pct: Optional[float]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/equity_trade.py backend/app/schemas/equity_trade.py
git commit -m "feat(equity-trades): add usd_rate to model and schemas"
```

---

## Task 3: Router — Lógica USD

**Files:**
- Modify: `backend/app/routers/equity_trades.py`

- [ ] **Step 1: Actualizar imports en `equity_trades.py`**

Cambiar la sección de imports al inicio de `backend/app/routers/equity_trades.py` para incluir `Quote`:

```python
from datetime import date, datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.equity_trade import EquityTrade
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.models.quote import Quote
from app.schemas.equity_trade import (
    EquityTradeCreate,
    EquityTradeOut,
    EquityTradeSummary,
    EquityTradeUpdate,
)
from app.services.equity_recalculate import recalculate_equity_positions

router = APIRouter(prefix="/api/equity-trades", tags=["equity-trades"])
```

- [ ] **Step 2: Actualizar `_trade_to_out` y agregar `_resolve_usd_rate`**

Reemplazar la función `_trade_to_out` y agregar `_resolve_usd_rate` debajo:

```python
def _trade_to_out(trade: EquityTrade) -> dict:
    return {
        "id": trade.id,
        "instrument_id": trade.instrument_id,
        "date": trade.date,
        "trade_type": trade.trade_type,
        "quantity": trade.quantity,
        "price": trade.price,
        "usd_rate": trade.usd_rate,
        "amount_brl": trade.amount_brl,
        "notes": trade.notes,
        "created_at": trade.created_at,
        "instrument_name": trade.instrument.name if trade.instrument else "",
        "instrument_ticker": trade.instrument.ticker if trade.instrument else None,
        "instrument_currency": trade.instrument.currency if trade.instrument else "BRL",
    }


def _resolve_usd_rate(
    instrument: Instrument,
    trade_date: date,
    provided_rate: Optional[float],
    db: Session,
) -> Optional[float]:
    if instrument.currency != "USD":
        return None
    if provided_rate is not None:
        return provided_rate
    month_start = date(trade_date.year, trade_date.month, 1)
    q = db.query(Quote).filter(Quote.date == month_start).first()
    return q.usd_brl if q and q.usd_brl else None
```

- [ ] **Step 3: Actualizar endpoint `GET /summary/{instrument_id}`**

Reemplazar la función `get_summary` completa:

```python
@router.get("/summary/{instrument_id}", response_model=EquityTradeSummary)
def get_summary(instrument_id: int, db: Session = Depends(get_db)):
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    is_usd = instrument.currency == "USD"
    trades = db.query(EquityTrade).filter(EquityTrade.instrument_id == instrument_id).all()

    total_compras_qty = sum(t.quantity for t in trades if t.trade_type == "compra")
    total_ventas_qty = sum(t.quantity for t in trades if t.trade_type == "venta")

    last_mp = (
        db.query(MonthlyPosition)
        .filter(MonthlyPosition.instrument_id == instrument_id)
        .order_by(MonthlyPosition.date.desc())
        .first()
    )
    qty_actual = last_mp.quantity if last_mp and last_mp.quantity is not None else 0.0
    avg_price_compra = last_mp.avg_price if last_mp else None

    last_priced_mp = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.unit_price.isnot(None),
        )
        .order_by(MonthlyPosition.date.desc())
        .first()
    )
    ultimo_precio = last_priced_mp.unit_price if last_priced_mp else None

    usd_rate_last = None
    if is_usd:
        if last_priced_mp and last_priced_mp.usd_rate:
            usd_rate_last = last_priced_mp.usd_rate
        else:
            from datetime import date as date_type
            today = date_type.today()
            q = db.query(Quote).filter(Quote.date == date(today.year, today.month, 1)).first()
            usd_rate_last = q.usd_brl if q and q.usd_brl else None

    pl_no_realizado = None
    pl_no_realizado_pct = None
    if ultimo_precio is not None and avg_price_compra is not None and qty_actual != 0:
        pl_no_realizado = qty_actual * (ultimo_precio - avg_price_compra)
        cost_basis = qty_actual * avg_price_compra
        if cost_basis != 0:
            pl_no_realizado_pct = (pl_no_realizado / abs(cost_basis)) * 100

    return EquityTradeSummary(
        instrument_id=instrument_id,
        instrument_name=instrument.name,
        instrument_ticker=instrument.ticker,
        currency=instrument.currency,
        is_usd=is_usd,
        total_compras_qty=total_compras_qty,
        total_ventas_qty=total_ventas_qty,
        qty_actual=qty_actual,
        avg_price_compra=avg_price_compra,
        ultimo_precio=ultimo_precio,
        usd_rate_last=usd_rate_last,
        pl_no_realizado=pl_no_realizado,
        pl_no_realizado_pct=pl_no_realizado_pct,
    )
```

- [ ] **Step 4: Actualizar endpoint `POST /`**

Reemplazar la función `create_trade` completa:

```python
@router.post("/")
def create_trade(body: EquityTradeCreate, db: Session = Depends(get_db)):
    instrument = db.query(Instrument).filter(Instrument.id == body.instrument_id).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    usd_rate = _resolve_usd_rate(instrument, body.date, body.usd_rate, db)
    if instrument.currency == "USD" and usd_rate is None:
        raise HTTPException(
            status_code=422,
            detail="No hay cotización USD/BRL para ese mes. Ingresá el rate manualmente.",
        )

    amount_brl = body.quantity * body.price * usd_rate if usd_rate else body.quantity * body.price

    trade = EquityTrade(
        instrument_id=body.instrument_id,
        date=body.date,
        trade_type=body.trade_type,
        quantity=body.quantity,
        price=body.price,
        usd_rate=usd_rate,
        amount_brl=amount_brl,
        notes=body.notes,
        created_at=datetime.utcnow(),
    )
    db.add(trade)
    db.flush()

    recalculated = recalculate_equity_positions(body.instrument_id, body.date, db)
    db.commit()
    db.refresh(trade)

    result = _trade_to_out(trade)
    result["recalculated_months"] = recalculated
    result["affected_from"] = body.date.strftime("%Y-%m")
    return result
```

- [ ] **Step 5: Actualizar endpoint `PUT /{trade_id}`**

Reemplazar la función `update_trade` completa:

```python
@router.put("/{trade_id}")
def update_trade(trade_id: int, body: EquityTradeUpdate, db: Session = Depends(get_db)):
    trade = db.query(EquityTrade).filter(EquityTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Operación no encontrada")

    old_date = trade.date

    if body.date is not None:
        trade.date = body.date
    if body.trade_type is not None:
        trade.trade_type = body.trade_type
    if body.quantity is not None:
        trade.quantity = body.quantity
    if body.price is not None:
        trade.price = body.price
    if body.notes is not None:
        trade.notes = body.notes

    instrument = db.query(Instrument).filter(Instrument.id == trade.instrument_id).first()
    usd_rate = _resolve_usd_rate(instrument, trade.date, body.usd_rate, db)
    if instrument and instrument.currency == "USD" and usd_rate is None:
        raise HTTPException(
            status_code=422,
            detail="No hay cotización USD/BRL para ese mes. Ingresá el rate manualmente.",
        )

    if usd_rate is not None:
        trade.usd_rate = usd_rate
    trade.amount_brl = (
        trade.quantity * trade.price * trade.usd_rate
        if trade.usd_rate
        else trade.quantity * trade.price
    )

    from_date = min(old_date, trade.date)
    db.flush()

    recalculated = recalculate_equity_positions(trade.instrument_id, from_date, db)
    db.commit()
    db.refresh(trade)

    result = _trade_to_out(trade)
    result["recalculated_months"] = recalculated
    result["affected_from"] = from_date.strftime("%Y-%m")
    return result
```

- [ ] **Step 6: Iniciar backend y verificar con curl**

```bash
cd backend && python3 -m uvicorn app.main:app --port 8000 &
sleep 2

# Buscar un instrumento USD existente
curl -s "http://localhost:8000/api/instruments?currency=USD&limit=5" | python3 -m json.tool | grep -E '"id"|"ticker"|"currency"'
```

Si hay instrumentos USD, tomar su ID para los siguientes tests. Si no hay, crear uno temporal:

```bash
curl -s -X POST "http://localhost:8000/api/instruments" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test USD ETF","ticker":"TEST","custodian":"XP_INTERNATIONAL","type":"accion","currency":"USD","location":"exterior"}' \
  | python3 -m json.tool
```

- [ ] **Step 7: Verificar POST con instrumento USD**

Usar el `instrument_id` del instrumento USD del paso anterior. Primero verificar que falla sin rate:

```bash
# Debe retornar 422 si no hay cotización en DB para ese mes
curl -s -X POST "http://localhost:8000/api/equity-trades/" \
  -H "Content-Type: application/json" \
  -d '{"instrument_id": <USD_ID>, "date": "2026-06-10", "trade_type": "compra", "quantity": 10, "price": 50.0}' \
  | python3 -m json.tool
```

Luego con rate manual:

```bash
curl -s -X POST "http://localhost:8000/api/equity-trades/" \
  -H "Content-Type: application/json" \
  -d '{"instrument_id": <USD_ID>, "date": "2026-06-10", "trade_type": "compra", "quantity": 10, "price": 50.0, "usd_rate": 5.75}' \
  | python3 -m json.tool
```

Esperado: `amount_brl` = 2875.0 (10 × 50 × 5.75), `usd_rate` = 5.75, `instrument_currency` = "USD"

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/equity_trades.py
git commit -m "feat(equity-trades): add USD support to router (resolve rate, amount_brl, summary)"
```

---

## Task 4: Servicio de Recálculo — Soporte USD

**Files:**
- Modify: `backend/app/services/equity_recalculate.py`

- [ ] **Step 1: Agregar `_get_monthly_rate` y actualizar imports**

En `backend/app/services/equity_recalculate.py`, cambiar los imports al inicio:

```python
import logging
from datetime import date
from calendar import monthrange
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.equity_trade import EquityTrade
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.services.snapshot_sync import sync_snapshot_for_date

logger = logging.getLogger(__name__)


def _get_monthly_rate(d: date, db: Session) -> Optional[float]:
    from app.models.quote import Quote
    month_start = date(d.year, d.month, 1)
    q = db.query(Quote).filter(Quote.date == month_start).first()
    return q.usd_brl if q and q.usd_brl else None
```

- [ ] **Step 2: Actualizar `recalculate_equity_positions` — detección de moneda**

Al inicio de la función `recalculate_equity_positions`, después de la línea `from_month = from_date.replace(day=1)`, agregar:

```python
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    is_usd = instrument.currency == "USD" if instrument else False
```

- [ ] **Step 3: Actualizar cálculo de `balance_brl`**

Buscar el bloque:

```python
        # Si hay unit_price, recalcular balance_brl
        if mp.unit_price is not None:
            mp.balance_brl = round(running_qty * mp.unit_price, 2)
```

Reemplazarlo por:

```python
        # Si hay unit_price, recalcular balance_brl
        if mp.unit_price is not None:
            if is_usd:
                rate = mp.usd_rate or _get_monthly_rate(mp.date, db)
                if rate:
                    mp.balance_brl = round(running_qty * mp.unit_price * rate, 2)
            else:
                mp.balance_brl = round(running_qty * mp.unit_price, 2)
```

- [ ] **Step 4: Actualizar cálculo de `net_trade_flow` para gain**

Buscar el bloque:

```python
        if prev_mp and prev_mp.balance_brl and prev_mp.balance_brl > 0:
            net_trade_flow = sum(
                t.quantity * t.price if t.trade_type == "compra" else -(t.quantity * t.price)
                for t in trades_of_month
            )
```

Reemplazarlo por:

```python
        if prev_mp and prev_mp.balance_brl and prev_mp.balance_brl > 0:
            if is_usd:
                net_trade_flow = sum(
                    (t.quantity * t.price * (t.usd_rate or 1.0) if t.trade_type == "compra"
                     else -(t.quantity * t.price * (t.usd_rate or 1.0)))
                    for t in trades_of_month
                )
            else:
                net_trade_flow = sum(
                    t.quantity * t.price if t.trade_type == "compra" else -(t.quantity * t.price)
                    for t in trades_of_month
                )
```

- [ ] **Step 5: Verificar avg_price en USD**

Con el trade del Task 3, verificar que el avg_price queda en USD. Hacer una segunda compra:

```bash
curl -s -X POST "http://localhost:8000/api/equity-trades/" \
  -H "Content-Type: application/json" \
  -d '{"instrument_id": <USD_ID>, "date": "2026-06-15", "trade_type": "compra", "quantity": 5, "price": 52.0, "usd_rate": 5.75}' \
  | python3 -m json.tool

# Verificar summary: avg_price debe ser (10*50 + 5*52) / 15 = 50.67 (en USD)
curl -s "http://localhost:8000/api/equity-trades/summary/<USD_ID>" | python3 -m json.tool
```

Esperado: `avg_price_compra` ≈ 50.67, `currency` = "USD", `is_usd` = true

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/equity_recalculate.py
git commit -m "feat(equity-trades): update recalculate service for USD instruments"
```

---

## Task 5: TypeScript — Tipos API

**Files:**
- Modify: `frontend/src/api/equityTrades.ts`

- [ ] **Step 1: Actualizar interfaces**

Reemplazar el contenido completo de `frontend/src/api/equityTrades.ts`:

```typescript
import client from './client';

export interface EquityTradeOut {
  id: number;
  instrument_id: number;
  date: string;
  trade_type: 'compra' | 'venta';
  quantity: number;
  price: number;
  usd_rate: number | null;
  amount_brl: number | null;
  notes: string | null;
  created_at: string;
  instrument_name: string;
  instrument_ticker: string | null;
  instrument_currency: string;
}

export interface EquityTradeWithRecalc extends EquityTradeOut {
  recalculated_months: number;
  affected_from: string;
}

export interface EquityTradeSummary {
  instrument_id: number;
  instrument_name: string;
  instrument_ticker: string | null;
  currency: string;
  is_usd: boolean;
  total_compras_qty: number;
  total_ventas_qty: number;
  qty_actual: number;
  avg_price_compra: number | null;
  ultimo_precio: number | null;
  usd_rate_last: number | null;
  pl_no_realizado: number | null;
  pl_no_realizado_pct: number | null;
}

export interface PaginatedTrades {
  items: EquityTradeOut[];
  total: number;
  page: number;
  pages: number;
}

export interface GetTradesParams {
  instrument_id?: number;
  date_from?: string;
  date_to?: string;
  trade_type?: string;
  page?: number;
  limit?: number;
}

export interface EquityTradeCreate {
  instrument_id: number;
  date: string;
  trade_type: 'compra' | 'venta';
  quantity: number;
  price: number;
  usd_rate?: number;
  notes?: string;
}

export interface EquityTradeUpdate {
  date?: string;
  trade_type?: 'compra' | 'venta';
  quantity?: number;
  price?: number;
  usd_rate?: number;
  notes?: string;
}

export async function getEquityTrades(params: GetTradesParams = {}): Promise<PaginatedTrades> {
  const res = await client.get('/api/equity-trades/', { params });
  return res.data;
}

export async function createEquityTrade(data: EquityTradeCreate): Promise<EquityTradeWithRecalc> {
  const res = await client.post('/api/equity-trades/', data);
  return res.data;
}

export async function updateEquityTrade(id: number, data: EquityTradeUpdate): Promise<EquityTradeWithRecalc> {
  const res = await client.put(`/api/equity-trades/${id}`, data);
  return res.data;
}

export async function deleteEquityTrade(id: number): Promise<void> {
  await client.delete(`/api/equity-trades/${id}`);
}

export async function getEquityTradeSummary(instrumentId: number): Promise<EquityTradeSummary> {
  const res = await client.get(`/api/equity-trades/summary/${instrumentId}`);
  return res.data;
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && bun run typecheck
```

Esperado: sin errores. Si hay errores, corregirlos antes de continuar.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/equityTrades.ts
git commit -m "feat(equity-trades): update TypeScript API types for USD support"
```

---

## Task 6: EquityTradeForm — Detección USD + Rate Lookup

**Files:**
- Modify: `frontend/src/components/EquityTradeForm.tsx`

- [ ] **Step 1: Actualizar `InstrumentOption` y agregar estado USD**

Reemplazar el contenido completo de `frontend/src/components/EquityTradeForm.tsx`:

```typescript
import { useState, useEffect, useRef } from 'react';
import client from '../api/client';
import { EquityTradeCreate, EquityTradeUpdate } from '../api/equityTrades';

interface InstrumentOption {
  id: number;
  name: string;
  ticker: string | null;
  currency: string;
}

interface Props {
  initialValues?: {
    instrument_id?: number;
    instrument_name?: string;
    instrument_ticker?: string | null;
    instrument_currency?: string;
    date?: string;
    trade_type?: 'compra' | 'venta';
    quantity?: number;
    price?: number;
    usd_rate?: number | null;
    notes?: string;
  };
  onSubmit: (data: EquityTradeCreate | EquityTradeUpdate) => Promise<void>;
  submitLabel?: string;
  isEdit?: boolean;
}

function parseBR(val: string): number {
  return parseFloat(val.replace(/\./g, '').replace(',', '.'));
}

export default function EquityTradeForm({ initialValues, onSubmit, submitLabel = 'Registrar Operación', isEdit = false }: Props) {
  const today = new Date().toISOString().split('T')[0];

  const [instrumentSearch, setInstrumentSearch] = useState(
    initialValues?.instrument_ticker
      ? `${initialValues.instrument_ticker} — ${initialValues.instrument_name}`
      : initialValues?.instrument_name || ''
  );
  const [instrumentId, setInstrumentId] = useState<number | null>(initialValues?.instrument_id ?? null);
  const [instrumentCurrency, setInstrumentCurrency] = useState<string>(initialValues?.instrument_currency ?? 'BRL');
  const [instrumentOptions, setInstrumentOptions] = useState<InstrumentOption[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [tradeType, setTradeType] = useState<'compra' | 'venta'>(initialValues?.trade_type ?? 'compra');
  const [date, setDate] = useState(initialValues?.date ?? today);
  const [quantity, setQuantity] = useState(initialValues?.quantity?.toString().replace('.', ',') ?? '');
  const [price, setPrice] = useState(initialValues?.price?.toString().replace('.', ',') ?? '');
  const [usdRateStr, setUsdRateStr] = useState(
    initialValues?.usd_rate != null ? initialValues.usd_rate.toString().replace('.', ',') : ''
  );
  const [usdRateFromDb, setUsdRateFromDb] = useState<number | null>(null);
  const [usdRateOverride, setUsdRateOverride] = useState(initialValues?.usd_rate != null);
  const [notes, setNotes] = useState(initialValues?.notes ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isUsd = instrumentCurrency === 'USD';
  const qtyNum = parseBR(quantity) || 0;
  const priceNum = parseBR(price) || 0;
  const effectiveRate = usdRateOverride ? (parseBR(usdRateStr) || null) : usdRateFromDb;
  const amountUsd = isUsd && qtyNum > 0 && priceNum > 0 ? qtyNum * priceNum : null;
  const amountBrl = amountUsd != null && effectiveRate ? amountUsd * effectiveRate : (!isUsd && qtyNum > 0 && priceNum > 0 ? qtyNum * priceNum : null);

  // Fetch USD rate from DB when instrument is USD and date changes
  useEffect(() => {
    if (!isUsd) return;
    const month = date.slice(0, 7);
    client.get('/api/quotes/lookup', { params: { month } })
      .then(r => {
        setUsdRateFromDb(r.data.rate ?? null);
        if (!usdRateOverride) {
          setUsdRateStr(r.data.rate != null ? r.data.rate.toString().replace('.', ',') : '');
        }
      })
      .catch(() => setUsdRateFromDb(null));
  }, [isUsd, date]);

  // Fetch instruments on search change
  useEffect(() => {
    if (instrumentSearch.length < 2) {
      setInstrumentOptions([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(() => {
      client.get('/api/instruments', { params: { search: instrumentSearch, status: 'activo', limit: 20 } })
        .then(r => {
          const items: InstrumentOption[] = r.data?.items ?? r.data ?? [];
          setInstrumentOptions(items);
          setShowDropdown(true);
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [instrumentSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelectInstrument = (inst: InstrumentOption) => {
    setInstrumentId(inst.id);
    setInstrumentCurrency(inst.currency ?? 'BRL');
    setInstrumentSearch(inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name);
    setShowDropdown(false);
    setUsdRateOverride(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const qty = parseBR(quantity);
    const prc = parseBR(price);

    if (!isEdit && !instrumentId) { setError('Seleccioná un instrumento'); return; }
    if (isNaN(qty) || qty <= 0) { setError('Cantidad debe ser mayor a 0'); return; }
    if (isNaN(prc) || prc <= 0) { setError('Precio debe ser mayor a 0'); return; }

    const finalRate = effectiveRate;
    if (isUsd && !finalRate) {
      setError('Ingresá la cotización USD/BRL');
      return;
    }

    setSubmitting(true);
    try {
      if (isEdit) {
        const data: EquityTradeUpdate = {
          date,
          trade_type: tradeType,
          quantity: qty,
          price: prc,
          notes: notes || undefined,
          ...(isUsd && finalRate ? { usd_rate: finalRate } : {}),
        };
        await onSubmit(data);
      } else {
        const data: EquityTradeCreate = {
          instrument_id: instrumentId!,
          date,
          trade_type: tradeType,
          quantity: qty,
          price: prc,
          notes: notes || undefined,
          ...(isUsd && finalRate ? { usd_rate: finalRate } : {}),
        };
        await onSubmit(data);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Error al guardar');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Instrumento */}
      {!isEdit && (
        <div className="relative" ref={dropdownRef}>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Instrumento</label>
          <input
            className="input w-full"
            placeholder="Buscar por ticker o nombre..."
            value={instrumentSearch}
            onChange={e => { setInstrumentSearch(e.target.value); setInstrumentId(null); setInstrumentCurrency('BRL'); }}
            onFocus={() => instrumentOptions.length > 0 && setShowDropdown(true)}
            autoComplete="off"
          />
          {showDropdown && instrumentOptions.length > 0 && (
            <div className="absolute z-50 left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg max-h-56 overflow-y-auto">
              {instrumentOptions.map(inst => (
                <button
                  key={inst.id}
                  type="button"
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  onClick={() => handleSelectInstrument(inst)}
                >
                  <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 mr-2">{inst.ticker ?? '—'}</span>
                  <span className="text-gray-700 dark:text-gray-300">{inst.name}</span>
                  {inst.currency === 'USD' && (
                    <span className="ml-2 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded font-semibold">USD</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tipo */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Tipo</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTradeType('compra')}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
              tradeType === 'compra'
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-emerald-400'
            }`}
          >
            Compra
          </button>
          <button
            type="button"
            onClick={() => setTradeType('venta')}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
              tradeType === 'venta'
                ? 'bg-rose-600 border-rose-600 text-white'
                : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-rose-400'
            }`}
          >
            Venta
          </button>
        </div>
      </div>

      {/* Fecha */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Fecha</label>
        <input
          type="date"
          className="input w-full"
          value={date}
          onChange={e => setDate(e.target.value)}
          required
        />
      </div>

      {/* Cantidad y Precio */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cantidad</label>
          <input
            className="input w-full"
            placeholder="0"
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {isUsd ? 'Precio (USD)' : 'Precio (BRL)'}
          </label>
          <input
            className="input w-full"
            placeholder="0,00"
            value={price}
            onChange={e => setPrice(e.target.value)}
            required
          />
        </div>
      </div>

      {/* Cotización USD/BRL — solo para instrumentos USD */}
      {isUsd && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Cotización USD/BRL
            </label>
            {usdRateFromDb != null && !usdRateOverride && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Del mes · <button type="button" className="text-indigo-500 hover:underline" onClick={() => setUsdRateOverride(true)}>Editar</button>
              </span>
            )}
          </div>
          {usdRateFromDb != null && !usdRateOverride ? (
            <div className="input w-full bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono cursor-default">
              1 USD = R$ {usdRateFromDb.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
            </div>
          ) : (
            <input
              className="input w-full"
              placeholder="Ej: 5,75"
              value={usdRateStr}
              onChange={e => setUsdRateStr(e.target.value)}
              required={isUsd}
            />
          )}
          {usdRateFromDb == null && (
            <p className="text-xs text-amber-500 mt-1">No hay cotización registrada para este mes. Ingresá el rate manualmente.</p>
          )}
        </div>
      )}

      {/* Monto total calculado */}
      <div>
        <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Monto total</label>
        {isUsd ? (
          <div className="input w-full bg-gray-50 dark:bg-gray-800 font-mono cursor-not-allowed space-y-0.5">
            <div className="text-blue-600 dark:text-blue-400">
              {amountUsd != null
                ? `USD ${amountUsd.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : '—'}
            </div>
            <div className="text-gray-500 dark:text-gray-400 text-xs">
              {amountBrl != null
                ? `≈ R$ ${amountBrl.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : effectiveRate ? '—' : 'ingresá la cotización'}
            </div>
          </div>
        ) : (
          <div className="input w-full bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono cursor-not-allowed">
            {amountBrl != null
              ? amountBrl.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
              : '—'}
          </div>
        )}
      </div>

      {/* Notas */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notas (opcional)</label>
        <textarea
          className="input w-full resize-none"
          rows={2}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Corretora, orden, etc."
        />
      </div>

      {error && <p className="text-sm text-rose-500">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="btn-primary w-full disabled:opacity-50"
      >
        {submitting ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
            Guardando...
          </span>
        ) : submitLabel}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Actualizar `initialValues` en `EquityTrades.tsx` para pasar `instrument_currency` y `usd_rate` al form de edición**

En `frontend/src/pages/EquityTrades.tsx`, buscar el bloque donde se pasa `initialValues` al `EquityTradeForm` en modo edición:

```typescript
            initialValues={{
              instrument_id: editTrade.instrument_id,
              instrument_name: editTrade.instrument_name,
              instrument_ticker: editTrade.instrument_ticker,
              date: editTrade.date,
              trade_type: editTrade.trade_type as 'compra' | 'venta',
              quantity: editTrade.quantity,
              price: editTrade.price,
              notes: editTrade.notes ?? '',
            }}
```

Reemplazarlo por:

```typescript
            initialValues={{
              instrument_id: editTrade.instrument_id,
              instrument_name: editTrade.instrument_name,
              instrument_ticker: editTrade.instrument_ticker,
              instrument_currency: editTrade.instrument_currency,
              date: editTrade.date,
              trade_type: editTrade.trade_type as 'compra' | 'venta',
              quantity: editTrade.quantity,
              price: editTrade.price,
              usd_rate: editTrade.usd_rate,
              notes: editTrade.notes ?? '',
            }}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && bun run typecheck
```

Esperado: sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/EquityTradeForm.tsx frontend/src/pages/EquityTrades.tsx
git commit -m "feat(equity-trades): add USD detection and rate lookup to trade form"
```

---

## Task 7: Tabla de Operaciones — Display USD

**Files:**
- Modify: `frontend/src/pages/EquityTrades.tsx`

- [ ] **Step 1: Actualizar columna "Precio Unit." en la tabla**

En `frontend/src/pages/EquityTrades.tsx`, buscar la celda de precio:

```typescript
                      <td className="px-3 py-2.5 text-right font-mono text-gray-700 dark:text-gray-300">
                        {trade.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
```

Reemplazarla por:

```typescript
                      <td className="px-3 py-2.5 text-right font-mono text-gray-700 dark:text-gray-300">
                        {trade.instrument_currency === 'USD' && (
                          <span className="text-xs text-blue-500 dark:text-blue-400 mr-1">USD</span>
                        )}
                        {trade.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
```

- [ ] **Step 2: Agregar columna "Monto USD" en el header y en las filas**

En el `<thead>`, después de la columna "Monto Total", agregar:

```typescript
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Monto USD</th>
```

En el `<tbody>`, después de la celda `amount_brl`, agregar:

```typescript
                      <td className="px-3 py-2.5 text-right font-mono text-gray-500 dark:text-gray-400 text-xs">
                        {trade.usd_rate && trade.amount_brl
                          ? `$${(trade.amount_brl / trade.usd_rate).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : '—'}
                      </td>
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && bun run typecheck
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EquityTrades.tsx
git commit -m "feat(equity-trades): show USD prefix on price column and USD amount in table"
```

---

## Task 8: EquityTradeSummaryCard — Display USD

**Files:**
- Modify: `frontend/src/components/EquityTradeSummaryCard.tsx`

- [ ] **Step 1: Actualizar el componente para manejar instrumentos USD**

Reemplazar el contenido completo de `frontend/src/components/EquityTradeSummaryCard.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { getEquityTradeSummary, EquityTradeSummary } from '../api/equityTrades';

interface Props {
  instrumentId: number;
}

export default function EquityTradeSummaryCard({ instrumentId }: Props) {
  const [summary, setSummary] = useState<EquityTradeSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getEquityTradeSummary(instrumentId)
      .then(setSummary)
      .finally(() => setLoading(false));
  }, [instrumentId]);

  if (loading) {
    return (
      <div className="card animate-pulse h-24 flex items-center justify-center">
        <span className="text-gray-400 text-sm">Cargando resumen...</span>
      </div>
    );
  }

  if (!summary) return null;

  const isUsd = summary.is_usd;
  const plPositive = summary.pl_no_realizado != null && summary.pl_no_realizado >= 0;
  const plColor = summary.pl_no_realizado == null
    ? 'text-gray-400'
    : plPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400';

  const fmtBRL = (v: number | null) =>
    v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 });

  const fmtUSD = (v: number | null) =>
    v == null ? '—' : `USD ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const fmtQty = (v: number) =>
    v.toLocaleString('pt-BR', { maximumFractionDigits: 4 });

  const fmtPrice = (v: number | null) =>
    v == null ? '—' : v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const plBrl = isUsd && summary.pl_no_realizado != null && summary.usd_rate_last
    ? summary.pl_no_realizado * summary.usd_rate_last
    : null;

  return (
    <div className="card border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
            {summary.instrument_ticker && (
              <span className="font-mono text-indigo-600 dark:text-indigo-400 mr-1.5">{summary.instrument_ticker}</span>
            )}
            {summary.instrument_name}
          </span>
          {isUsd && (
            <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded font-semibold">USD</span>
          )}
        </div>
        {summary.qty_actual < 0 && (
          <span className="text-xs bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 px-2 py-0.5 rounded-full border border-rose-200 dark:border-rose-700 font-semibold">
            Cantidad negativa
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Cantidad actual</p>
          <p className={`font-mono font-semibold ${summary.qty_actual < 0 ? 'text-rose-500' : 'text-gray-800 dark:text-gray-200'}`}>
            {fmtQty(summary.qty_actual)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Precio prom. compra</p>
          <p className="font-mono font-semibold text-gray-800 dark:text-gray-200">
            {isUsd
              ? fmtUSD(summary.avg_price_compra)
              : `R$ ${fmtPrice(summary.avg_price_compra)}`}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Último precio</p>
          <p className="font-mono font-semibold text-gray-800 dark:text-gray-200">
            {isUsd
              ? fmtUSD(summary.ultimo_precio)
              : `R$ ${fmtPrice(summary.ultimo_precio)}`}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">P&L no realizado</p>
          {isUsd ? (
            <div>
              <p className={`font-mono font-semibold ${plColor}`}>
                {fmtUSD(summary.pl_no_realizado)}
                {summary.pl_no_realizado_pct != null && (
                  <span className="ml-1 text-xs">
                    ({summary.pl_no_realizado_pct >= 0 ? '+' : ''}{summary.pl_no_realizado_pct.toFixed(2)}%)
                  </span>
                )}
              </p>
              {plBrl != null && (
                <p className="text-xs text-gray-400 dark:text-gray-500 font-mono mt-0.5">
                  ≈ {fmtBRL(plBrl)}
                </p>
              )}
            </div>
          ) : (
            <p className={`font-mono font-semibold ${plColor}`}>
              {fmtBRL(summary.pl_no_realizado)}
              {summary.pl_no_realizado_pct != null && (
                <span className="ml-1 text-xs">
                  ({summary.pl_no_realizado_pct >= 0 ? '+' : ''}{summary.pl_no_realizado_pct.toFixed(2)}%)
                </span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck final**

```bash
cd frontend && bun run typecheck
```

Esperado: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EquityTradeSummaryCard.tsx
git commit -m "feat(equity-trades): show USD prices and dual-currency P&L in summary card"
```

---

## Task 9: Verificación End-to-End

- [ ] **Step 1: Levantar sistema completo**

```bash
# Terminal 1 — Backend
cd backend && python3 -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && bun run dev
```

- [ ] **Step 2: Verificar instrumentos BRL sin cambios**

En el browser (`http://localhost:5173`), ir a Operaciones, seleccionar un instrumento BRL (ej. una acción B3), crear una operación. Verificar:
- Label del precio sigue siendo `Precio (BRL)`
- No aparece campo de cotización
- Monto total se muestra en BRL como antes

- [ ] **Step 3: Verificar instrumento USD**

Seleccionar un instrumento con `currency=USD`. Verificar:
- Badge `USD` aparece en el dropdown de búsqueda
- Al seleccionar, el label cambia a `Precio (USD)`
- Aparece campo "Cotización USD/BRL" — si hay rate en DB para el mes actual, se muestra automáticamente; si no, aparece el aviso ámbar con campo manual
- Monto total muestra `USD X,XX` y `≈ R$ X,XX`

- [ ] **Step 4: Registrar una operación USD y verificar en tabla**

Registrar compra de 10 unidades a USD 50,00 con rate 5,75. En la tabla verificar:
- Columna "Precio Unit." muestra `USD 50,00`
- Columna "Monto Total" muestra `R$ 2.875,00`
- Columna "Monto USD" muestra `$500,00` (= 2875 / 5.75 ≈ 500)

- [ ] **Step 5: Verificar Summary Card**

Filtrar por el instrumento USD. El card debe mostrar:
- Badge `USD`
- "Precio prom. compra" en `USD X,XX`
- "Último precio" en `USD X,XX`
- P&L en USD con equivalente BRL

- [ ] **Step 6: Verificar que operaciones BRL existentes no se ven afectadas**

Revisar el historial de operaciones BRL en la tabla — deben aparecer sin prefijo USD, columna "Monto USD" vacía (`—`).

- [ ] **Step 7: Commit final de documentación**

Actualizar `CONTEXT.md` en la sección de Features Implementados, agregar:

```
- [x] Operaciones USD: precio en USD, cotización mensual auto-detectada desde tabla quotes, amount_brl calculado, avg_price en USD, display dual USD/BRL en formulario y resumen
```

```bash
git add CONTEXT.md
git commit -m "docs: update CONTEXT.md with equity trades USD feature"
```
