from fastapi import APIRouter

from app.expenses.routers import accounts, fx, imports, rules

router = APIRouter()
router.include_router(accounts.router)
router.include_router(fx.router)
router.include_router(imports.router)
router.include_router(rules.router)
