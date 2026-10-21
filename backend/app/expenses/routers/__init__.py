from fastapi import APIRouter

from app.expenses.routers import accounts, fx

router = APIRouter()
router.include_router(accounts.router)
router.include_router(fx.router)
