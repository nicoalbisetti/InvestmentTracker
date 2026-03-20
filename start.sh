#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "=========================================="
echo "  InvestmentTracker — Iniciando sistema"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 no encontrado. Instalar desde https://python.org"
  exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js no encontrado. Instalar desde https://nodejs.org"
  exit 1
fi

# ---- Backend ----
echo "[1/4] Instalando dependencias del backend..."
cd "$BACKEND"
pip3 install -r requirements.txt -q

# Import initial data if DB does not exist or is empty
DB_FILE="$BACKEND/investment_tracker.db"
EXCEL_FILE="$ROOT/Inversiones.xlsx"

if [ ! -f "$DB_FILE" ]; then
  if [ -f "$EXCEL_FILE" ]; then
    echo "[2/4] Importando datos iniciales desde Inversiones.xlsx..."
    python3 import_initial_data.py "$EXCEL_FILE"
  else
    echo "[2/4] Base de datos no encontrada. Creando estructura vacía..."
    python3 -c "from app.database import create_tables; create_tables()"
    echo "       (Puedes importar datos luego desde Configuración > Importar Excel)"
  fi
else
  echo "[2/4] Base de datos existente encontrada, omitiendo importación."
fi

# Start backend in background
echo "[3/4] Iniciando backend FastAPI en http://127.0.0.1:8000 ..."
cd "$BACKEND"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# ---- Frontend ----
echo "[4/4] Iniciando frontend React en http://localhost:5173 ..."
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
  echo "       Instalando dependencias npm..."
  npm install -q
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "  Sistema iniciado correctamente"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API Docs : http://localhost:8000/docs"
echo "=========================================="
echo ""
echo "Presiona Ctrl+C para detener ambos servidores."
echo ""

# Wait and forward signals
cleanup() {
  echo ""
  echo "Deteniendo servidores..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

wait $BACKEND_PID $FRONTEND_PID
