from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import create_tables
from app.routers import (
    dashboard, positions, history, annual, proventos, provento_forecast,
    transactions, instruments, quotes, import_excel
)
from app.routers import import_fixed_income
from app.routers import import_proventos
from app.routers import equity_trades

app = FastAPI(
    title="InvestmentTracker API",
    description="Sistema de seguimiento de inversiones personales",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno: {exc}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.on_event("startup")
def startup():
    from app.database import _migrate_provento_items
    from app.database import engine as main_engine, demo_engine, _migrate_provento_items
    _migrate_provento_items(main_engine)
    _migrate_provento_items(demo_engine)
    create_tables()


app.include_router(dashboard.router)
app.include_router(positions.router)
app.include_router(history.router)
app.include_router(annual.router)
app.include_router(provento_forecast.router)
app.include_router(proventos.router)
app.include_router(transactions.router)
app.include_router(instruments.router)
app.include_router(quotes.router)
app.include_router(import_excel.router)
app.include_router(import_fixed_income.router)
app.include_router(import_proventos.router)
app.include_router(equity_trades.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/env")
def get_env(request: Request):
    env = request.headers.get("X-Env", "production")
    return {"env": env}


@app.post("/api/demo/regenerate")
def regenerate_demo():
    import subprocess, sys, os
    script = os.path.join(os.path.dirname(__file__), "..", "create_demo_db.py")
    result = subprocess.run(
        [sys.executable, os.path.abspath(script)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"ok": True, "output": result.stdout}
