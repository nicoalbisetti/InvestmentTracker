# InvestmentTracker

Sistema web de seguimiento de inversiones personales. Reemplaza y supera la funcionalidad de un Excel con mas de 150 instrumentos y datos desde enero 2015.

## Stack

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy + SQLite
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Recharts

## Inicio rapido

```bash
./start.sh
```

El script automaticamente:
1. Instala dependencias de Python y Node.js
2. Importa los datos de `Inversiones.xlsx` (si existe en la raiz del proyecto)
3. Levanta el backend en `http://localhost:8000`
4. Levanta el frontend en `http://localhost:5173`

## Requisitos previos

- Python 3.11+
- Node.js 18+
- pip3

## Instalacion manual

### Backend

```bash
cd backend
pip3 install -r requirements.txt
python3 import_initial_data.py ../Inversiones.xlsx   # Importar datos iniciales
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Importar datos

Hay dos formas de importar el Excel:

**Via script (recomendado para el primer uso):**
```bash
cd backend
python3 import_initial_data.py /ruta/al/Inversiones.xlsx
```

**Via interfaz web:**
1. Abrir `http://localhost:5173`
2. Ir a Configuracion > Importar Excel
3. Arrastrar el archivo o hacer clic para seleccionar
4. Ver el reporte de importacion con conteos, warnings y errores

## Paginas

| Pagina | URL | Descripcion |
|--------|-----|-------------|
| Dashboard | `/` | KPIs, evolucion historica, distribucion, top/bottom 5 |
| Posiciones | `/positions` | Tabla con todos los instrumentos activos, filtros y sort |
| Evolucion | `/history` | Graficos historicos por instrumento o comparativos |
| Anual | `/annual` | Resumen por anio con graficos |
| Proventos | `/proventos` | Dividendos y rendimientos por instrumento |
| Transacciones | `/transactions` | CRUD de operaciones manuales |
| Configuracion | `/settings` | Importar Excel, editar catalogo de instrumentos |

## API

La documentacion interactiva de la API esta disponible en:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Endpoints principales:
```
GET  /api/dashboard/kpis
GET  /api/dashboard/evolution
GET  /api/dashboard/distribution
GET  /api/positions
GET  /api/positions/export     (CSV)
GET  /api/history/{id}
GET  /api/annual
GET  /api/proventos
GET  /api/transactions
POST /api/transactions
POST /api/import               (upload Excel)
GET  /api/import/history
```

## Estructura del proyecto

```
InvestmentTracker/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   └── services/
│   ├── import_initial_data.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── api/
│   │   └── utils/
│   └── package.json
├── start.sh
└── README.md
```
