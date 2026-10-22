from sqlalchemy import Column, Date, Float, String

from app.expenses.db import ExpBase

PAIR_USDBRL = "USDBRL_PTAX"
PAIR_USDARS = "USDARS_MEP"


class ExpFxRate(ExpBase):
    __tablename__ = "exp_fx_rates"

    date = Column(Date, primary_key=True)
    pair = Column(String, primary_key=True)  # USDBRL_PTAX | USDARS_MEP
    rate = Column(Float, nullable=False)
    source = Column(String, nullable=False)  # ptax | argentinadatos | manual
