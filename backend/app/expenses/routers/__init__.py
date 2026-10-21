from fastapi import APIRouter

from app.expenses.routers import accounts, fx, imports, reports, rules, transactions

router = APIRouter()
router.include_router(accounts.router)
router.include_router(fx.router)
router.include_router(imports.router)
router.include_router(rules.router)
router.include_router(transactions.router)
router.include_router(reports.router)
