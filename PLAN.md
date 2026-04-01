# InvestmentTracker — Plan de Desarrollo

## Vision General

Sistema web fullstack para seguimiento de cartera de inversiones personales.
Reemplaza un Excel con 5.637 filas de datos historicos desde enero 2015.

---

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy ORM |
| Base de datos | SQLite (auto-creada al iniciar) |
| Frontend | React 18 + TypeScript + Vite |
| Graficos | Recharts |
| Estilos | Tailwind CSS + shadcn/ui |
| Importacion Excel | pandas + openpyxl |
| HTTP Client | Axios |
| Estado global | React Context / Zustand |

---

## Estructura de Directorios

```
InvestmentTracker/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, startup
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── instrument.py     # Catalogo maestro
│   │   │   ├── monthly_position.py
│   │   │   ├── portfolio_snapshot.py
│   │   │   ├── annual_summary.py
│   │   │   ├── provento.py
│   │   │   ├── quote.py
│   │   │   └── transaction.py
│   │   ├── routers/
│   │   │   ├── dashboard.py      # KPIs, graficos principales
│   │   │   ├── positions.py      # Posiciones actuales / ranking
│   │   │   ├── history.py        # Evolucion historica por instrumento
│   │   │   ├── annual.py         # Resumen anual
│   │   │   ├── proventos.py      # Dividendos y proventos
│   │   │   ├── transactions.py   # CRUD transacciones manuales
│   │   │   ├── instruments.py    # Catalogo (CRUD)
│   │   │   ├── quotes.py         # Cotizaciones USD/BRL
│   │   │   └── import_excel.py   # Importador Excel
│   │   ├── services/
│   │   │   ├── importer.py       # Logica de parseo por hoja
│   │   │   ├── performance.py    # Calculos: CAGR, drawdown, rankings
│   │   │   └── cache.py          # Invalidacion de cache
│   │   └── schemas/              # Pydantic schemas (request/response)
│   ├── seed_data.py              # Script: 24 meses datos de prueba
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Positions.tsx
│   │   │   ├── History.tsx
│   │   │   ├── Annual.tsx
│   │   │   ├── Proventos.tsx
│   │   │   ├── Transactions.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── layout/           # Sidebar, Header, Breadcrumbs
│   │   │   ├── charts/           # AreaChart, BarChart, DonutChart
│   │   │   ├── tables/           # DataTable con sort/filter
│   │   │   └── ui/               # Cards, Modals, Skeleton loaders
│   │   ├── api/                  # Axios hooks por dominio
│   │   ├── context/              # Theme (dark/light), Auth
│   │   └── utils/                # Formatters BRL/USD/%, fechas
│   ├── package.json
│   └── vite.config.ts
├── start.sh                      # Levanta backend + frontend en un comando
├── README.md
└── .gitignore
```

---

## Modelos de Base de Datos

### Instrument
Catalogo maestro de instrumentos.
- id, name, custodian, type (renta_fija/accion/fii/fondo/exterior/cripto/etc.)
- currency (BRL/USD), maturity_date, liquidity (D+2/D+30/etc.)
- status (activo/cerrado/sin_datos), created_at

### MonthlyPosition
Posiciones mensuales historicas (hoja Saldos).
- instrument_id (FK), date (normalizado al dia 1 del mes)
- balance_brl, balance_usd, usd_rate
- applications, redemptions, gain, gain_pct, proventos
- UNIQUE constraint: (instrument_id, date)

### PortfolioSnapshot
Snapshot mensual del portfolio completo (hoja Resumen).
- date, total_brl, total_usd, usd_rate, monthly_change_pct
- totales por custodio: hsbc_total, bradesco_total, xp_br_total, xp_us_total, etc.

### AnnualSummary
Resumen anual (hoja Totales).
- year, total, diff, gain, net_flow

### Provento
Dividendos por instrumento y periodo.
- instrument_id (FK), year, month (nullable), amount

### Quote
Cotizaciones historicas (hoja Cotizaciones).
- date, usd_brl, bvmf3_price

### Transaction
Transacciones manuales.
- instrument_id (FK), date, type (aplicacion/rescate/provento/otro)
- amount_brl, amount_usd, notes, created_at

---

## Logica del Importador Excel

### Hoja Saldos (header en fila 1, datos desde fila 2)
- Columnas: Mes, Banco, Fondo, Preço médio, Indice, Saldo USD, Cot USD, Saldo BRL, Aplicaciones, Rescates, Saldo calculado, Saldo anterior, Ganancia, Ganancia (%), Proventos
- Crear Instrument si no existe (clave: Banco + Fondo)
- Normalizar fecha al dia 1 del mes
- Upsert por (instrument_id, date)
- Ignorar filas con Saldo BRL = 0 o NaN

### Hoja Resumen (header en fila 0, datos desde fila 1)
- Primera columna = fechas, resto = instrumentos o columnas de totales
- Columnas de totales van a PortfolioSnapshot
- Ignorar columnas Unnamed
- Columna Incremento = monthly_change_pct

### Hoja Cotizaciones (header en fila 0)
- Columnas: Fechas, Dolar, BVMF3
- Upsert por date

### Hoja Totales (header en fila 1)
- Datos desde fila 2
- Ignorar ultima fila 'Totales' (es acumulado)

### Hoja Ranking (header en fila 3, datos desde fila 4, tabla desde columna 5)
- Columnas: Fondo, Venc, Saldo, Porc, Ultimo mes, Ranking ult mes, Ultimos 3 meses, [rank], Ultimos 6 meses, [rank], Ultimo ano, [rank]
- Actualiza campos de ranking en Instrument

### Hoja Proventos (header en fila 3, datos desde fila 4, tabla desde columna 5)
- Columnas: Fondo, Saldo, Proventos 2026, 2025, 2024, 2023, 2022...
- Upsert proventos anuales por instrumento

---

## API REST — Endpoints Principales

```
GET  /api/dashboard/kpis              # KPIs principales
GET  /api/dashboard/evolution         # Serie historica del portfolio
GET  /api/dashboard/distribution      # Por tipo y por custodio
GET  /api/dashboard/top-bottom        # Top 5 / Bottom 5 del mes

GET  /api/positions                   # Posiciones actuales (con filtros, paginacion)
GET  /api/positions/export            # CSV

GET  /api/history/:instrument_id      # Historia de un instrumento
GET  /api/history/compare             # Comparacion multi-instrumento
GET  /api/history/monthly             # Matriz mensual: instrumentos × 12 meses (filtros: custodian, type, market)
GET  /api/history/annual              # Matriz anual: instrumentos × últimos 10 años

GET  /api/annual                      # Resumen anual
GET  /api/proventos                   # Proventos por instrumento
GET  /api/proventos/monthly           # Proventos mensuales del anio actual

GET  /api/transactions                # Listado (filtros, paginacion)
POST /api/transactions                # Nueva transaccion
PUT  /api/transactions/:id
DEL  /api/transactions/:id

GET  /api/instruments                 # Catalogo
PUT  /api/instruments/:id             # Editar tipo/custodio/vencimiento
GET  /api/quotes                      # Cotizaciones
POST /api/quotes                      # Ingresar cotizacion manual

POST /api/import                      # Importar Excel (multipart)
GET  /api/import/history              # Historial de importaciones
```

---

## Paginas de la Interfaz

| Pagina | Ruta | Descripcion |
|--------|------|-------------|
| Dashboard | `/` | KPIs, grafico evolucion, donut distribucion, top/bottom 5 |
| Posiciones | `/positions` | Tabla ranking con filtros y sort |
| Histórico | `/history` | Matriz instrumento × período (mensual/anual), filtros custodio/tipo/mercado, toggle BRL/USD |
| Anual | `/annual` | Tabla + grafico barras apiladas |
| Proventos | `/proventos` | Tabla + grafico mensual + proyeccion |
| Transacciones | `/transactions` | CRUD transacciones manuales |
| Configuracion | `/settings` | Catalogo instrumentos, importacion, cotizacion |

---

## Fases de Desarrollo

### Fase 1 — Backend Core (modelos + DB + importador)
1. Setup del proyecto FastAPI + SQLAlchemy + SQLite
2. Crear los 7 modelos con auto-creacion de DB
3. Implementar importador Excel con logica por hoja
4. Tests manuales del importador con Inversiones.xlsx

### Fase 2 — API REST (endpoints)
5. Router dashboard (KPIs, evolucion, distribucion)
6. Router positions (con filtros, paginacion, export CSV)
7. Routers history, annual, proventos
8. Router transactions (CRUD completo)
9. Routers instruments, quotes, import

### Fase 3 — Frontend base
10. Setup React + Vite + TypeScript + Tailwind
11. Layout: sidebar, header, dark/light toggle, breadcrumbs
12. Pagina Dashboard con todos sus componentes
13. Pagina Posiciones con tabla ordenable y filtros

### Fase 4 — Frontend resto de paginas
14. [x] Histórico — matriz mensual/anual (instrumento × período, filtros, BRL/USD toggle)
15. Analisis Anual
16. Proventos y dividendos
17. Transacciones (formulario + lista)
18. Configuracion (catalogo + importacion drag&drop)

### Fase 5 — Datos y entregables finales
19. Script seed_data.py con 24 meses de datos de prueba
20. README.md con instrucciones de instalacion
21. start.sh para levantar el sistema en un comando
22. Import del Inversiones.xlsx y validacion de coherencia

### Fase 6 — GitHub + ClickUp
23. Inicializar repo Git, crear repo en GitHub, push de todos los archivos (excepto Inversiones.xlsx)
24. Crear tareas en ClickUp por fase

---

## Tareas ClickUp (estructura)

**Lista: InvestmentTracker**

- [FASE 1] Backend Core
  - Setup FastAPI + SQLAlchemy + SQLite
  - Crear 7 modelos ORM
  - Implementar importador Excel (6 hojas)
  - Validar importacion con Inversiones.xlsx

- [FASE 2] API REST
  - Endpoints Dashboard
  - Endpoints Positions + export CSV
  - Endpoints History + Annual + Proventos
  - CRUD Transactions
  - Endpoints Instruments + Quotes + Import

- [FASE 3] Frontend Base
  - Setup React + Vite + Tailwind
  - Layout (sidebar, header, dark/light)
  - Pagina Dashboard
  - Pagina Posiciones

- [FASE 4] Frontend Resto
  - [x] Histórico — matriz mensual/anual implementada
  - Analisis Anual
  - Proventos
  - Transacciones
  - Configuracion

- [FASE 5] Entregables
  - seed_data.py
  - README.md
  - start.sh
  - Validacion final con datos reales

- [FASE 6] Infraestructura
  - Repo GitHub + push
  - Tareas ClickUp

---

## Issues del Excel que el sistema resuelve

| Problema | Solucion |
|----------|----------|
| Fechas inconsistentes (dia 1 vs dia 15) | Normalizacion al dia 1 al importar |
| Instrumentos cerrados sin distincion | Status activo/cerrado/sin_datos |
| Mezcla BRL/USD sin separacion | Campos separados balance_brl y balance_usd |
| Sin validacion de consistencia | Warnings y errores en reporte de importacion |
| Sin visualizacion | Dashboards con Recharts |
| Sin proyecciones ni alertas | Proyeccion proventos, alerta vencimientos <90 dias |

---

*Plan generado el 20/03/2026 — InvestmentTracker v1.0*
