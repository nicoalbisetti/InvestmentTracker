from sqlalchemy import Boolean, Column, Integer, String

from app.expenses.db import ExpBase


class ExpEntity(ExpBase):
    __tablename__ = "exp_entities"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)  # personal | bertioga | pj
    name = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
