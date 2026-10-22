# CONTEXT-expenses.md — Módulo de Gastos

> Documento de contexto del módulo de gastos. Estado real del código al 22 Oct 2026.
> El resto del sistema (inversiones) está en `CONTEXT.md`. Este módulo es **independiente**: base SQLite propia,
> paquete propio, y sólo `services/linking.py` lee las tablas de inversiones (siempre en modo lectura).

---

## 1. Qué hace

Importa extractos de cuentas, billeteras y tarjetas de Argentina y Brasil, clasifica cada movimiento (gasto, ingreso,
transferencia propia, pago de tarjeta, aporte/rescate de inversión, provento, cambio de moneda), lo concilia con otras
cuentas y con Inversiones/Proventos, y muestra gasto por categoría, mes y entidad (Personal, Bertioga, PJ).

- Moneda consolidada: **BRL**. Cada movimiento guarda además moneda nativa y USD (`amount`, `amount_brl`, `amount_usd`).
- Cuotas: se imputan por **cuota pagada** (mes del vencimiento de la fatura). Se guarda `n/N` y `purchase_date`.
- Los flujos de inversión, las transferencias propias, los pagos de tarjeta con fatura y los cambios de moneda
  **no** son gasto ni ingreso.

## 2. Límites del módulo y privacidad

- Backend en `backend/app/expenses/`. Tablas con prefijo `exp_` en una **base SQLite separada**
  (`backend/expenses.db` real y `backend/expenses_demo.db` demo; URLs por `EXPENSES_DATABASE_URL` /
  `EXPENSES_DEMO_DATABASE_URL`). Sin FKs hacia tablas de inversiones.
- Entorno real/demo: `get_exp_db` (`app/expenses/db.py`) elige la base por el header `X-Env`, igual que `get_db`.
- `tests/expenses/test_architecture.py` hace cumplir: nada fuera de `app/expenses/` (salvo `main.py`) importa el módulo,
  y dentro del módulo sólo `services/linking.py` importa código que no sea de `app.expenses`.
- **Nunca se commitea**: `docs/expenses/` (extractos reales), `backend/app/expenses/seed/*.local.json` (reglas con
  nombres reales), `backend/tests/expenses/*golden*.json`, `exports/`, `*.db`. Está en `.gitignore`.
- No se persiste el nombre original del archivo (`file_label` = formato + 8 chars del hash). Los parsers no guardan
  CUIT/CBU/nº de cuenta/domicilio; los números de 8+ dígitos en descripciones se enmascaran (`***1234`).
- `owner_identifiers` (nombres propios) viven sólo en la base de gastos; el listado de cuentas no los devuelve
  (sólo `GET /accounts/{id}`).

## 3. Modelo de datos (`app/expenses/models/`)

| Tabla | Campos clave |
|---|---|
| `exp_entities` | `code` (personal \| bertioga \| pj), `name`, `active` |
| `exp_accounts` | `name`, `institution`, `country` (AR\|BR), `kind` (bank\|wallet\|credit_card), `currency`, `parser_key`, `owner_identifiers` (JSON), `paid_from_account_id`, `default_entity_id`, `has_statements`, `active` |
| `exp_import_batches` | `account_id`, `file_label`, `file_hash` (UNIQUE con `account_id`), `parser_key`, `period_start/end`, `statement_due_date`, `statement_period` (YYYY-MM), `statement_totals` (JSON por moneda), `validation` (JSON de checks), `preview_rows` (JSON mientras `status=preview`), `status` (preview\|confirmed\|discarded) |
| `exp_categories` | `name` (UNIQUE), `is_system`. Sistema: "Tarjeta sin detalle", "Sin clasificar" |
| `exp_transactions` | `account_id`, `batch_id`, `date` (imputación), `purchase_date`, `statement_period`, `description_raw`, `counterparty`, `merchant_normalized`, `external_id`, `amount` (con signo), `currency`, `fx_usd_brl`, `fx_ars_usd`, `fx_estimated`, `amount_brl`, `amount_usd`, `kind`, `category_id`, `entity_id`, `installment_number/total`, `classification_source` (own_account\|rule\|manual\|default), `rule_id`, `needs_review`, `transfer_group_id`, `statement_batch_id`, `dedup_hash` (UNIQUE) |
| `exp_rules` | `priority`, `account_id`, `field`, `pattern` (regex i), `amount_sign`, `set_kind`, `set_category_id`, `set_entity_id`, `origin` (seed\|manual), `seed_key` |
| `exp_links` | Vínculos **hacia Inversiones**: `exp_transaction_id`, `target_type` (investment_transaction\|provento_item), `target_id`, `link_type`, `amount_allocated_brl`, `status` (suggested\|confirmed\|rejected), `score`, y snapshot `target_date/target_amount/target_label` |
| `exp_fx_rates` | PK `(date, pair)`: `USDBRL_PTAX`, `USDARS_MEP`; `rate`, `source` (ptax\|argentinadatos\|manual) |

`kind`: `expense · refund · income · own_transfer · card_payment · investment_contribution · investment_withdrawal ·
provento · fx_conversion · unknown`. Signos esperados: expense/aporte < 0; refund/income/provento/rescate > 0
(si no cumplen → `needs_review`).

**Vínculos internos como columnas** (no en `exp_links`): `transfer_group_id` (= menor id del par de transferencias o de
pago de tarjeta) y `statement_batch_id` (pago de la cuenta pagadora → fatura que cubre).

Migraciones: tablas nuevas las crea `create_all`; cambios futuros en `app/expenses/migrations.py` (`run_migrations`).

## 4. Parsers (`app/expenses/parsers/`)

Interfaz: `StatementParser` (`key`, `detect(filename, head_bytes)`, `parse(path, **opts)`) → `ParsedStatement`
(filas `ParsedRow` + `validation: list[Check]` + `declared_totals` + `account_hint`). Registro en `registry.py`;
`detect_parser` devuelve el único parser que reconoce el archivo (los PDF se detectan por **contenido**).
Importes con `Decimal` (`numbers.parse_money`: `R$`, `-R$`, `$ -x`, `x-`, `US$`, `$ 103.091 80`).
Convención de signo: movimiento que saca dinero < 0. En tarjetas: consumo < 0, pago/devolución > 0.

| `parser_key` | Formato | Particularidades |
|---|---|---|
| `xp_account_csv` | CSV `;` UTF-8 BOM, descendente | Reconstruye el orden por **cadena de saldos** (los empates de segundo vienen en orden ascendente) |
| `xp_card_csv` | Fatura XP, CSV | Vencimiento desde el nombre `FaturaYYYY-MM-DD.csv` (o `due_date` en el import); pago de la fatura anterior vs devolución |
| `inter_account_csv` | CSV con preámbulo | Ascendente; contraparte de `Cp :<ISPB>-<nombre>`; no guarda el nº de cuenta |
| `mercadopago_pdf` | PDF en pesos + sección en dólares | Descripción multilínea por **celdas** (filetes) y coordenadas; filas USD con sus checks |
| `santander_ar_account_pdf` | PDF cuenta Santander AR | Celdas por filetes, columnas caja de ahorro/cuenta corriente, fecha centrada verticalmente; ignora páginas de consumos de tarjeta |
| `santander_ar_card_pdf` | PDF resumen VISA y AMEX Santander | Una línea = un movimiento por columnas (x); año/mes arrastrados; `SU PAGO` = pesos efectivamente debitados (incluye USD × TC); `TRANSFERENCIA DEUDA` = `fx_conversion` |

**Checks de validación** (por archivo; si alguno falla, confirmar exige `force`): saldo corrido, saldo final declarado,
Σ entradas/salidas, líneas con fecha parseadas, y para tarjetas AR `saldo anterior − pagos + movimientos = DEBITAREMOS`
(ARS y USD) y `Σ consumos = Total Consumos`.

## 5. Importación (`services/importer.py`, `routers/imports.py`)

Flujo: detectar → parsear → elegir cuenta (único candidato por `parser_key`; la marca VISA/AMEX desambigua) → dedup →
FX → clasificar → **preview** (JSON en el lote) → confirmar (con overrides manuales y `force`) → `linking.rebuild`.
- Mismo archivo para la misma cuenta ⇒ **409**. Faltan datos ⇒ 422 con `candidates` o `needs_due_date`.
- Borrar un lote confirmado elimina exactamente sus filas, sus vínculos y libera pares; luego recalcula cobertura.
- **Dedup** (`services/dedup.py`): con `external_id` (comprobante/ID de operación) clave natural; si no, hash de los campos
  + ordinal de ocurrencia entre filas idénticas del archivo (las 14 EASYJET de R$ 10 siguen siendo 14). Centavos enteros.

## 6. Clasificación (`services/classifier.py`, `services/rules.py`, `services/normalize.py`)

Orden: transferencia propia por `owner_identifiers` (sólo en descripciones de transferencia: Pix/TED/Transferência) →
reglas por `priority` → pista del parser (`card_payment`/`refund`) → default (`Sin clasificar`, `needs_review`).
Una regla `expense` sobre un importe positivo da `refund` (y viceversa). Las clasificaciones `manual` nunca se pisan.
Seeds: `seed/rules.example.json` (commiteado, nombres de ejemplo) y `seed/rules.local.json` (ignorado, reales);
carga idempotente por `seed_key`. Crear regla desde una corrección (`PATCH /transactions/{id}` con `create_rule`)
reclasifica sólo las filas `needs_review` no manuales que matchean (`POST /rules/preview` muestra el impacto).

## 7. Conciliación (`services/linking.py`)

- **Pares** (`own_transfer`, `card_payment`): otra cuenta, mismo importe/moneda, signo opuesto; auto-confirma lo
  inequívoco (≤ 1 día en transferencias; 45 días en tarjetas). Ambiguos → sugerencias en la cola.
- **Adopción**: una transferencia propia sin par adopta a su contraparte exacta no reconocida (±1 día, única, no manual).
- **Tarjetas por cobertura**: un pago de la cuenta pagadora dentro de la ventana de vencimiento de una fatura
  importada queda cubierto (`statement_batch_id`) aunque el monto no coincida (parciales, cargos, USD × TC). Si el
  pago nombra una marca (visa/amex/mastercard) sólo lo cubre una fatura de esa marca. Sin fatura ⇒ se cuenta como
  **"Tarjeta sin detalle"** y deja de contarse sola al importar la fatura. Exacto = monto igual al total o par con el
  crédito de la fatura siguiente.
- **Inversiones/proventos** (`link_investments`, `link_proventos`): sólo **sugiere**. Aporte/rescate ↔ `Transaction`
  (±30 días; exacto 0,5 %; FGC hasta 6 % y sólo instrumentos `in_liquidation`; 1 movimiento = hasta 3 transacciones);
  una transferencia propia entrante sin par puede ser la contraparte exacta de un rescate. Cobro ↔ `ProvéntoItem`
  (1→N y N→1, sin filtrar por custodia). Confirmar descarta alternativas; un rechazo no se vuelve a sugerir.
- **Auditoría** (`audit_investments`, sólo lectura): movimientos sin Transaction, Transactions de custodias importadas
  sin movimiento bancario, diferencias en vínculos confirmados, vínculos cuyo destino cambió.

## 8. Resumen (`services/summary.py`)

Fuente única de verdad (`bucket`): **gasto** = `expense` + `refund` (netea) + pagos de tarjeta sin fatura cubierta;
**ingreso** = `income`; **provento** aparte; todo lo demás excluido. Filtros: meses, entidad (la de la fila o la
default de la cuenta), país, moneda (BRL \| USD \| native). Devuelve por mes: gasto, ingreso, proventos, ahorro,
por categoría y por entidad, `no_detail`, % pendiente de revisar y **cobertura** de extractos por cuenta y mes.

## 9. Tipos de cambio (`services/fx.py`)

PTAX venta (BCB Olinda; sólo días hábiles → día anterior) y MEP venta (argentinadatos, por día calendario). Cache en
`exp_fx_rates`; no vuelve a bajar series que el cache ya cubre. Si la API falla usa el último valor y marca
`fx_estimated`. Carga manual (`PUT /fx/rates`) nunca se pisa; `POST /fx/recompute?from&to` recalcula un rango.

## 10. Endpoints (`/api/expenses`)

| Método | Ruta | Descripción |
|---|---|---|
| GET/POST/PATCH | `/accounts`, `/accounts/{id}` | Cuentas (identificadores propios sólo en el detalle) |
| POST | `/imports` | Multipart `file`, `account_id?`, `due_date?` → preview (checks, duplicados, clasificación) |
| POST | `/imports/{id}/confirm` | Body `{account_id?, overrides[], force}` |
| GET/DELETE | `/imports`, `/imports/{id}` | Historial; borrar (preview o lote confirmado) |
| GET | `/transactions` | Filtros kind, category_id, entity, account_id, country, from, to, needs_review, q; paginado |
| PATCH | `/transactions/{id}` | `kind`, `category_id`, `entity_id`, `notes`, `create_rule` |
| POST | `/transactions/bulk` | `{ids[], kind?, category_id?, entity_id?}` |
| GET | `/summary` | `from`, `to` (YYYY-MM), `entity`, `country`, `currency` |
| GET | `/review-queue` | Sin clasificar, signo, pares sugeridos, transferencias sin par, pagos de tarjeta sin fatura/inexactos, inversiones y proventos sin vincular, FX |
| GET | `/coverage` | Meses con extracto por cuenta |
| POST | `/links/rebuild` | Pares + adopción + fatura + sugerencias de inversiones/proventos |
| POST/DELETE | `/links/pairs`, `/links/pairs/{group_id}` | Confirmar/romper un par |
| GET | `/links/suggestions?status=` | Vínculos con inversiones agrupados por movimiento |
| POST | `/links/{id}/confirm`, `/links/{id}/reject` | |
| GET | `/audit/investments?from&to` | Auditoría de sólo lectura |
| GET/POST | `/rules`, `/rules/preview` | Reglas; vista previa de impacto; alta con `apply_to_pending` |
| GET/POST | `/categories`; GET `/entities` | |
| PUT/GET | `/fx/rates`; POST `/fx/recompute` | Tipos de cambio manuales / recálculo por rango |
| POST | `/demo/regenerate` | Regenera los datos ficticios de la base **demo** (ignora el header) |

## 11. Frontend (`/gastos`)

`src/pages/expenses/GastosPage.tsx` con pestañas por `?tab=`: **Resumen** (KPIs, barras apiladas categoría × mes,
tabla, filtros, cobertura), **Movimientos** (filtros, edición inline, selección múltiple + edición masiva, "crear regla"
con confirmación del impacto), **Revisar** (cola por motivo, vincular pares, confirmar/rechazar vínculos con Inversiones,
auditoría), **Importar** (wizard + historial con borrado), **Configuración** (cuentas e identificadores propios).
Código: `src/components/expenses/*`, `src/api/expenses.ts`, `src/utils/expenses.ts`. Ítem "Gastos" en `Sidebar.tsx`
y ruta en `App.tsx` (únicos archivos de Inversiones tocados).

## 12. Operación

- Datos demo: `python -m app.expenses.seed.demo` (desde `backend/`) o `POST /api/expenses/demo/regenerate`; también se
  generan solos si la base demo no tiene cuentas. Son ficticios (sin identificadores).
- Carga real (T-10, 22 Oct 2026): 11 cuentas (AR: Santander cuenta/VISA/AMEX, Mercado Pago, Mastercard sin extractos;
  BR: XP cuenta/tarjeta, Inter cuenta/tarjeta sin extractos, Santander BR y Bradesco sin extractos) y los 41 archivos de
  `docs/expenses/` ⇒ 2.238 movimientos. Clasificado automático: XP cuenta 95 %, Inter 100 %, tarjeta XP 41 % (87 % por
  monto), Santander cuenta 23 %, Mercado Pago 58 %; total 52 % de filas / 87 % por monto. El resto se resuelve con
  "crear regla". Las métricas son in-sample (las reglas se escribieron mirando estos archivos).
- Tests: `cd backend && python3 -m pytest tests` (pytest + httpx en `requirements-dev.txt`). Los tests con extractos
  reales se saltean si `docs/expenses/` o `tests/expenses/real_golden.json` no existen. Los PDF sintéticos se generan
  con `tests/expenses/pdf_builder.py`.
- Frontend: lint de los archivos nuevos limpio; `npm run build`/`tsc -b` del repo ya fallaba **antes** del módulo
  (52 errores TS en páginas de Inversiones: Annual, Positions, ImportFixedIncome, etc.).

## 13. Pendientes y límites conocidos

- Compras de cripto (Brasil Bitcoin, Mercado Bitcoin, Alpha Trading) no existen como `Transaction` en Inversiones: la
  auditoría las lista como "sin transacción" (43 aportes).
- Transferencias propias hacia cuentas no importadas (Santander BR, Bradesco, cuenta de inversión) quedan como "sin par";
  no hay forma de indicar la cuenta de destino (idea: `counterparty_account_id` por regla).
- Una regla no puede marcar `needs_review` (p. ej. entidad de VIVO/Telefónica a confirmar).
- Sección de dólares de la cuenta Santander AR y AMEX con USD sólo cubiertas por PDF sintéticos (los extractos reales
  no traen movimientos en esos casos).
- No implementado de la spec: `installments/upcoming`, combobox con búsqueda, edición de reglas/TC en la UI, drag de
  prioridad de reglas. v2 (proyecciones, anomalías, cruces con inversiones) fuera de alcance.
