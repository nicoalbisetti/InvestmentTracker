from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables
from app.routers import (
    dashboard, positions, history, annual, proventos,
    transactions, instruments, quotes, import_excel
)

app = FastAPI(
    title="InvestmentTracker API",
    description="Sistema de seguimiento de inversiones personales",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


app.include_router(dashboard.router)
app.include_router(positions.router)
app.include_router(history.router)
app.include_router(annual.router)
app.include_router(proventos.router)
app.include_router(transactions.router)
app.include_router(instruments.router)
app.include_router(quotes.router)
app.include_router(import_excel.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
