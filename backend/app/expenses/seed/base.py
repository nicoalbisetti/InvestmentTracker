from sqlalchemy.orm import Session

from app.expenses.models import ExpCategory, ExpEntity

ENTITIES = [
    ("personal", "Personal"),
    ("bertioga", "Bertioga"),
    ("pj", "PJ"),
]

CATEGORIES = [
    "Supermercado", "Restaurantes y delivery", "Transporte", "Auto", "Viajes",
    "Hogar y mantenimiento", "Servicios", "Condominio / expensas", "Limpieza",
    "Salud y farmacia", "Ropa y calzado", "Suscripciones", "Educación", "Familia",
    "Ocio y entretenimiento", "Regalos", "Servicios profesionales", "Impuestos",
    "Cargos financieros", "Cargos bancarios", "Efectivo", "Rendimientos", "Otros",
]
SYSTEM_CATEGORIES = ["Tarjeta sin detalle", "Sin clasificar"]


def seed_base_data(db: Session) -> None:
    """Idempotente: sólo inserta lo que falta (por code / name)."""
    have_e = {e.code for e in db.query(ExpEntity.code)}
    for code, name in ENTITIES:
        if code not in have_e:
            db.add(ExpEntity(code=code, name=name))
    have_c = {c.name for c in db.query(ExpCategory.name)}
    for name in CATEGORIES:
        if name not in have_c:
            db.add(ExpCategory(name=name, is_system=False))
    for name in SYSTEM_CATEGORIES:
        if name not in have_c:
            db.add(ExpCategory(name=name, is_system=True))
    db.commit()
