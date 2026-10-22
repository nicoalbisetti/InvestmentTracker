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
| `exp_accounts` | `name`, `institution`, `country` (AR\|BR), `kind` (bank\|wallet\|credit_card), `currency`, `parser_key`, `owner_identifiers` (JSON), `paid_from_account_id`, `default_entity_id`, `has_statements`, `itemizes_investments` (el extracto detalla aportes/rescates por inversión; la auditoría sólo cruza esas custodias), `active` |
| `exp_import_batches` | `account_id`, `file_label`, `file_hash` (UNIQUE con `account_id`), `parser_key`, `period_start/end`, `statement_due_date`, `statement_period` (YYYY-MM), `statement_totals` (JSON por moneda), `validation` (JSON de checks), `preview_rows` (JSON mientras `status=preview`), `status` (preview\|confirmed\|discarded) |
| `exp_categories` | `name` (UNIQUE), `is_system`. Sistema: "Tarjeta sin detalle", "Sin clasificar" |
| `exp_transactions` | `account_id`, `batch_id`, `date` (imputación), `purchase_date`, `statement_period`, `description_raw`, `counterparty`, `merchant_normalized`, `external_id`, `amount` (con signo), `currency`, `fx_usd_brl`, `fx_ars_usd`, `fx_estimated`, `amount_brl`, `amount_usd`, `kind`, `category_id`, `entity_id`, `installment_number/total`, `classification_source` (own_account\|rule\|manual\|default), `rule_id`, `needs_review`, `transfer_group_id`, `statement_batch_id`, `counterparty_account_id` (cuenta propia de la otra punta, aunque no se importe), `exclude_from_audit` (aporte que no se rastrea en Inversiones, p. ej. cripto), `dedup_hash` (UNIQUE) |
| `exp_rules` | `priority`, `account_id`, `field`, `pattern` (regex i), `amount_sign`, `set_kind`, `set_category_id`, `set_entity_id`, `set_needs_review` (clasifica pero deja la fila en revisión), `set_counterparty_account_id`, `set_exclude_from_audit`, `origin` (seed\|manual), `seed_key` |
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

- **Pares** (`own_transfer`, `card_payment`): otra cuenta (si una fila declara `counterparty_account_id`, sólo esa), mismo importe/moneda, signo opuesto; auto-confirma lo
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
- **Auditoría** (`audit_investments`, sólo lectura): movimientos sin Transaction (salvo `exclude_from_audit`), Transactions de
  custodias cuyo extracto **detalla inversiones** (`itemizes_investments`) sin movimiento bancario, diferencias en vínculos confirmados, vínculos cuyo destino cambió.

## 8. Resumen (`services/summary.py`)

Fuente única de verdad (`bucket`): **gasto** = `expense` + `refund` (netea) + pagos de tarjeta sin fatura cubierta;
**ingreso** = `income` clasificado (las entradas sin clasificar —default + revisión— van aparte en `income_pending`, no suman); **provento** aparte; todo lo demás excluido. Filtros: meses, entidad (la de la fila o la
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
| PATCH/DELETE | `/rules/{id}` | Editar (una semilla editada pasa a `manual` y las recargas ya no la pisan; `apply_to_pending`) / borrar (sólo manuales: las semilla se desactivan) |
| POST | `/rules/reorder` | `{ids:[todas]}`: orden de evaluación; sólo cambian de prioridad las reglas que se mueven |
| POST | `/rules/reapply?include_rule_rows=` | Pasa los pendientes (no manuales) por las reglas vigentes; con `include_rule_rows=true` re-evalúa también las ya clasificadas por una regla |
| GET/POST | `/review/unpaired-groups`, `/review/unpaired-groups/apply` | Transferencias propias sin par agrupadas por descripción; asigna la cuenta de contraparte (regla + filas) y reintenta el pareo |
| GET | `/review/merchant-groups` | Pendientes agrupados por comercio y signo, de mayor a menor monto |
| POST | `/review/merchant-groups/apply` | `{items:[{key, sign, kind, category_id?, entity_id?}]}`: una regla anclada por comercio, aplicada a sus filas pendientes |
| GET/POST | `/categories`; GET `/entities` | |
| PUT/GET/DELETE | `/fx/rates`; POST `/fx/recompute` | Tipos de cambio: carga manual, listado, quitar una carga manual (restaura la fuente) / recálculo por rango |
| GET | `/installments/upcoming?months=` | Cuotas comprometidas por mes y tarjeta desde la última fatura importada (dato, no proyección) |
| POST | `/demo/regenerate` | Regenera los datos ficticios de la base **demo** (ignora el header) |

## 11. Frontend (`/gastos`)

`src/pages/expenses/GastosPage.tsx` con pestañas por `?tab=`: **Resumen** (KPIs, barras apiladas categoría × mes,
tabla, filtros, cobertura), **Movimientos** (filtros, edición inline, selección múltiple + edición masiva, "crear regla"
con confirmación del impacto), **Revisar** (comercios sin clasificar agrupados con "crear N reglas", cola por motivo, vincular pares, confirmar/rechazar vínculos con Inversiones,
auditoría), **Importar** (wizard + historial con borrado), **Configuración** (subsecciones: **Cuentas** e identificadores propios; **Reglas** —editar, activar, borrar, crear con vista previa de impacto y reordenar arrastrando—; **Tipos de cambio** —ver, cargar a mano, quitar y recalcular un rango—; **Categorías**). El Resumen incluye el bloque **Cuotas comprometidas**. Los selectores de categoría/entidad usan un `Combobox` con búsqueda (sin acentos, con teclado).
Código: `src/components/expenses/*`, `src/api/expenses.ts`, `src/utils/expenses.ts`. Ítem "Gastos" en `Sidebar.tsx`
y ruta en `App.tsx` (únicos archivos de Inversiones tocados).

## 12. Operación

- Datos demo: `python -m app.expenses.seed.demo` (desde `backend/`) o `POST /api/expenses/demo/regenerate`; también se
  generan solos si la base demo no tiene cuentas. Son ficticios (sin identificadores).
- Carga real (T-10, 22 Oct 2026): 11 cuentas (AR: Santander cuenta/VISA/AMEX, Mercado Pago, Mastercard sin extractos;
  BR: XP cuenta/tarjeta, Inter cuenta/tarjeta sin extractos, Santander BR y Bradesco sin extractos) y los 41 archivos de
  `docs/expenses/` ⇒ 2.238 movimientos. Clasificado automático: XP cuenta 95 %, Inter 100 %, tarjeta XP 41 % (87 % por
  monto), Santander cuenta 23 %, Mercado Pago 58 %; total 52 % de filas / 87 % por monto. El resto se resuelve con
  "crear regla". Las métricas son in-sample (las reglas se escribieron mirando estos archivos). Con las reglas genéricas
  agregadas el 22 Oct (derivadas sólo de ene–jun) quedó 56 % de filas clasificadas; en jul–sep (fuera de muestra) resolvieron 11 de 79
  pendientes. Lo que falta son sobre todo transferencias a personas (AR), que requieren tu criterio.
- Tests: `cd backend && python3 -m pytest tests` (pytest + httpx en `requirements-dev.txt`). Los tests con extractos
  reales se saltean si `docs/expenses/` o `tests/expenses/real_golden.json` no existen. Los PDF sintéticos se generan
  con `tests/expenses/pdf_builder.py`.
- Frontend: `cd frontend && npm run build` (tsc -b + vite build) pasa sin errores desde el 22 Oct 2026 (se corrigieron 52 errores
  de tipos previos en páginas de Inversiones, sin cambios de comportamiento). El lint de los archivos del módulo está limpio;
  el resto del repo conserva ~125 errores de lint históricos (`no-explicit-any`, etc.).

## 13. Pendientes y límites conocidos

- Transferencias propias hacia cuentas no importadas: se asigna la cuenta de la otra punta desde Revisar (o en Movimientos);
  las que van a una cuenta sin extractos dejan de ser sospechosas. Quedan por asignar las que van a otros bancos propios
  (Santander BR, Bradesco, Inter alterno): la descripción no dice a cuál, requiere tu criterio.
- Las cripto (Brasil Bitcoin, Mercado Bitcoin, Alpha Trading) se usan sólo para mandar plata de Brasil a Argentina: la regla
  `br_crypto_transfer` las clasifica como `fx_conversion` (ni gasto ni aporte a inversiones). El lado argentino (las entradas
  de personas/exchanges en Santander AR y Mercado Pago) no se puede reconocer solo: quedan sin clasificar y se marcan "Cambio de
  moneda" desde Revisar. Mientras estén sin clasificar **no suman a ingresos** (`income_pending` en el resumen).
- Las "conta investimento" de XP son dos cuentas; se modelan como una sola contraparte ("XP inversión (2 cuentas)", sin
  extractos) porque las descripciones no dicen a cuál va cada transferencia.
- La auditoría cruza sólo las custodias de cuentas con `itemizes_investments` (hoy Inter). XP no detalla (aportes por la
  "conta investimento").
- Sección en dólares de la cuenta Santander AR y consumos en USD de AMEX: no se usan (los 6 extractos reales dicen "sin movimientos en dólares"
  y las tarjetas no se usan en dólares). El código existe pero sólo está cubierto por PDF sintéticos; si algún día aparece un caso real y
  los controles de saldo no cierran, el import exige `force`.
- Sin clasificar: transferencias a personas (AR) en su mayoría; se resuelven con tu criterio en Revisar.
- Spec no implementada: sólo la v2 (proyecciones, anomalías, cruces con Inversiones), fuera de alcance.
- La base **demo** de gastos usa siempre `rules.example.json` (nunca `rules.local.json`) y `seed_demo` descarta todas sus reglas al regenerar.
