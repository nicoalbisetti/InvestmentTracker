# Equity Trades USD — Design Spec

**Date:** 2026-06-12  
**Status:** Approved

---

## Objetivo

Permitir registrar operaciones de renta variable (equity trades) en instrumentos denominados en USD. El precio se ingresa en USD y el sistema usa la cotización mensual almacenada en la tabla `quotes` para calcular el valor en BRL (`amount_brl`). El precio promedio (`avg_price`) se almacena en USD para instrumentos USD.

---

## Decisiones de Diseño

| Pregunta | Decisión |
|---|---|
| Cotización a usar | Rate mensual de tabla `quotes` (mismo patrón que Transacciones) |
| Moneda de `avg_price` | USD para instrumentos USD |
| Display en UI | Ambas monedas: USD + BRL en paralelo |
| Enfoque schema | Mínimo: agregar solo `usd_rate` a `equity_trades` |

---

## 1. Schema

### Nueva columna en `equity_trades`

```sql
ALTER TABLE equity_trades ADD COLUMN usd_rate REAL;
```

- `usd_rate`: rate USD/BRL usado al registrar el trade. `NULL` para instrumentos BRL.
- `price`: precio en **moneda nativa** del instrumento (USD para USD instruments, BRL para BRL instruments). Sin cambio semántico en los existentes.
- `amount_brl`: calculado como `qty * price * usd_rate` (USD) o `qty * price` (BRL).

### Migración

Nuevo archivo `backend/migrate_equity_trades_usd.py`, llamado en `startup()` de `main.py`:

```python
def _migrate_equity_trades_usd():
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(equity_trades)"))]
        if "usd_rate" not in cols:
            conn.execute(text("ALTER TABLE equity_trades ADD COLUMN usd_rate REAL"))
            conn.commit()
```

---

## 2. Backend

### `app/models/equity_trade.py`

Agregar:
```python
usd_rate = Column(Float, nullable=True)
```

### `app/schemas/equity_trade.py`

- `EquityTradeCreate`: agregar `usd_rate: Optional[float] = None`
- `EquityTradeUpdate`: agregar `usd_rate: Optional[float] = None`
- `EquityTradeOut`: agregar `usd_rate: Optional[float]`
- `EquityTradeSummary`: agregar `currency: str`, `is_usd: bool`

### `app/routers/equity_trades.py`

**Helper `_resolve_usd_rate(instrument, trade_date, provided_rate, db)`:**
- Si `instrument.currency != "USD"` → retorna `None`
- Si `provided_rate` viene en el body → lo usa directamente
- Si no → consulta `db.query(Quote).filter_by(date=date(year, month, 1)).first()` y retorna `q.usd_brl`
- Si tampoco hay en DB → retorna `None` (el frontend debería haberlo enviado)

**POST `/api/equity-trades/`:**
1. Llamar a `_resolve_usd_rate()`
2. Si `instrument.currency == "USD"` y `usd_rate` es `None` → HTTP 422: "No hay cotización USD/BRL para ese mes. Ingresá el rate manualmente."
3. `amount_brl = qty * price * usd_rate` si USD, `qty * price` si BRL
4. Guardar `usd_rate` en el trade

**PUT `/api/equity-trades/{id}`:**
- Misma lógica de `_resolve_usd_rate()` y recálculo de `amount_brl`

**GET `/api/equity-trades/summary/{instrument_id}`:**
- Agregar `currency = instrument.currency` e `is_usd = (instrument.currency == "USD")` al response

### `app/services/equity_recalculate.py`

Al inicio de `recalculate_equity_positions()`:
```python
instrument = db.query(Instrument).filter_by(id=instrument_id).first()
is_usd = instrument.currency == "USD"
```

**`avg_price`:** sin cambio — ya usa `t.price` que es en moneda nativa.

**`balance_brl`** (cuando `mp.unit_price is not None`):
```python
if is_usd:
    rate = mp.usd_rate or _get_monthly_rate(mp.date, db)
    mp.balance_brl = round(running_qty * mp.unit_price * rate, 2) if rate else mp.balance_brl
else:
    mp.balance_brl = round(running_qty * mp.unit_price, 2)
```

**`net_trade_flow`** para cálculo de `gain`:
```python
net_trade_flow = sum(
    (t.quantity * t.price * (t.usd_rate or 1) if t.trade_type == "compra"
     else -(t.quantity * t.price * (t.usd_rate or 1)))
    for t in trades_of_month
)
```

**Helper `_get_monthly_rate(d: date, db) -> Optional[float]`:** consulta `Quote` table por `date(d.year, d.month, 1)`.

---

## 3. Frontend

### `api/equityTrades.ts`

Agregar `usd_rate?: number` a `EquityTradeCreate`, `EquityTradeUpdate`, `EquityTradeOut`.  
Agregar `currency?: string`, `is_usd?: boolean` a `EquityTradeSummary`.

### `EquityTradeForm.tsx`

Al seleccionar un instrumento via `handleSelectInstrument()`:
- Fetch `GET /api/instruments/{id}` para obtener `currency` (o enriquecer `InstrumentOption` con `currency`)
- Guardar `instrumentCurrency` en estado

**Comportamiento si `instrumentCurrency === "USD"`:**
- Label precio: `Precio (USD)` en lugar de `Precio (BRL)`
- Fetch automático de `GET /api/quotes/lookup?month=YYYY-MM` cuando cambia la fecha
- Mostrar rate detectado: `Cotización del mes: 1 USD = R$ X,XX` (editable si el usuario quiere override)
- Si rate no encontrado en DB: campo de texto para ingresarlo manualmente (obligatorio para USD)
- Monto total: mostrar `USD X.XXX,XX` y `≈ R$ X.XXX,XX` en dos líneas
- Enviar `usd_rate` en el body

**Validación:** si instrumento USD y no hay `usd_rate` → bloquear submit con error `"Ingresá la cotización USD/BRL"`.

### `EquityTrades.tsx` (tabla)

- Columna **Precio Unit.**: prefijo `USD` o sin prefijo según `instrument.currency` (requiere enriquecer `EquityTradeOut` con `instrument_currency`)
- Columna **Monto Total**: sin cambio (siempre `amount_brl` en BRL)
- Agregar columna **Monto USD** opcional o tooltip cuando `usd_rate` está presente (`amount_brl / usd_rate`)

### `EquityTradeSummaryCard.tsx`

- Si `is_usd`: mostrar `avg_price_compra` y `ultimo_precio` con sufijo `USD`
- P&L no realizado: mostrar en USD + equivalente BRL entre paréntesis (usando el último `usd_rate` disponible del instrumento o del último `MonthlyPosition`)

---

## 4. Cambios a `EquityTradeOut`

Agregar `instrument_currency: str` (retornado en `_trade_to_out()` desde `trade.instrument.currency`).

---

## 5. Qué NO cambia

- Instrumentos BRL existentes: sin impacto. `usd_rate` queda `NULL`, lógica idéntica.
- `avg_price` para BRL: sin cambio.
- Importador XP International: ya maneja su propio flujo con `get_usd_brl_rate()`, independiente de este feature.

---

## 6. Tests / Verificación

- Crear operación compra en instrumento USD con rate manual → verificar `amount_brl = qty * price_usd * rate`
- Crear operación en instrumento USD con rate desde DB → verificar auto-fetch
- Verificar que `avg_price` queda en USD tras múltiples compras
- Verificar `balance_brl` recalculado correctamente en `MonthlyPosition`
- Verificar que operaciones BRL existentes no se ven afectadas
