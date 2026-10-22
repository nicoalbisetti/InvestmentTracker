from fastapi import APIRouter

from app.expenses.db import ExpDemoSessionLocal
from app.expenses.seed.demo import seed_demo

router = APIRouter(prefix="/api/expenses/demo", tags=["expenses"])


@router.post("/regenerate")
def regenerate_demo():
    """Regenera los datos ficticios de gastos. Opera siempre sobre la base DEMO, sin importar el header."""
    with ExpDemoSessionLocal() as s:
        return seed_demo(s)
