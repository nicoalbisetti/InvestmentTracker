from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int
