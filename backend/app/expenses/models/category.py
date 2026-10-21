from sqlalchemy import Boolean, Column, Integer, String

from app.expenses.db import ExpBase


class ExpCategory(ExpBase):
    __tablename__ = "exp_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    is_system = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
