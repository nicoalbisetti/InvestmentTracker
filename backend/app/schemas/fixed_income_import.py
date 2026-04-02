from __future__ import annotations
from typing import Optional, List, Literal
from datetime import date, datetime
from pydantic import BaseModel, Field


class ImportConfig(BaseModel):
    # Values
    import_values: bool = True
    import_value_curva: bool = True
    import_value_mtm: bool = True
    value_change_threshold_pct: Optional[float] = None

    # Quantities
    import_quantities: bool = True
    alert_quantity_change: bool = False

    # Instrument data
    import_instrument_data: bool = True
    import_maturity_date: bool = True
    import_issue_date: bool = True
    import_indexador: bool = True
    import_custodian: bool = True
    import_name: bool = False  # overwrite name — risky, default off

    # New instruments
    create_new_instruments: bool = True
    create_base_only: bool = False  # create instrument only, no position

    # Unit price
    import_unit_price: bool = True

    # Custodian filter
    custodian_filter: Optional[str] = None  # "XP" | "SANTANDER" | "INTER" | None = all


class ParsedInstrument(BaseModel):
    produto: str
    codigo: str
    tipo: str        # "CDB" | "CRI" | "CRA" | "DEB" | "LCA" | "LCI" | "LIG" | "CFF" | "TD"
    emissor: str
    custodian: str   # "XP" | "SANTANDER" | "INTER"
    custodian_override: Optional[str] = None  # set when same code appears in 2 custodians
    indexador: Optional[str] = None
    emissao: Optional[date] = None
    vencimento: Optional[date] = None
    quantidade: Optional[float] = None
    valor_brl: Optional[float] = None        # resolved value (MTM or CURVA)
    unit_price: Optional[float] = None       # resolved unit price
    valor_mtm: Optional[float] = None        # raw MTM value
    valor_curva: Optional[float] = None      # raw CURVA value
    capital_invested: Optional[float] = None  # Valor Aplicado (TD only)
    in_liquidation: bool = False


class DiffItem(BaseModel):
    status: Literal["NEW", "UPDATED", "UNCHANGED", "DISAPPEARED"]
    codigo: str
    nome: str
    tipo: str
    emissor: str
    custodian: str
    custodian_override: Optional[str] = None
    indexador: Optional[str] = None
    emissao: Optional[date] = None
    vencimento: Optional[date] = None
    in_liquidation: bool = False
    # Value comparison (None if import_values=False in config)
    valor_actual_brl: Optional[float] = None
    valor_anterior_brl: Optional[float] = None
    variacion_brl: Optional[float] = None
    variacion_pct: Optional[float] = None
    # Quantity comparison
    cantidad_actual: Optional[float] = None
    cantidad_anterior: Optional[float] = None
    # Unit price
    unit_price: Optional[float] = None
    capital_invested: Optional[float] = None
    # For DISAPPEARED items
    ultimo_valor_brl: Optional[float] = None
    ultima_fecha: Optional[date] = None
    # DB instrument id (None if NEW)
    instrument_id: Optional[int] = None
    # Warnings
    warnings: List[str] = Field(default_factory=list)


class PreviewSummary(BaseModel):
    total_in_file: int
    new_instruments: int
    updated_positions: int
    unchanged: int
    disappeared: int
    parse_errors: int
    no_price_available: int


class PreviewResponse(BaseModel):
    file_token: str
    period_date: date
    summary: PreviewSummary
    differences: List[DiffItem]
    parse_warnings: List[str]
    expires_at: datetime


class ConfirmRequest(BaseModel):
    file_token: str
    period_date: str   # "YYYY-MM-DD"
    config: ImportConfig
    skip_codes: List[str] = Field(default_factory=list)  # (codigo, custodian_override) pairs as "codigo::override"


class ImportResult(BaseModel):
    success: bool
    imported: dict  # {new_instruments, new_positions, updated_positions}
    skipped: int
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class MapInstrumentRequest(BaseModel):
    codigo_excel: str
    instrument_id: int
    file_token: Optional[str] = None          # update in-memory diff if provided
    custodian_override: Optional[str] = None  # needed to identify the right DiffItem
