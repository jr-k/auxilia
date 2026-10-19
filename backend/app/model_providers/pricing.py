"""Catalog prices in USD per token, using Langfuse usage-type names."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field


Rate = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class TokenPrices(BaseModel):
    input: Rate
    input_cache_read: Rate
    output: Rate
    # Cache writes are optional because most providers bill them as input.
    input_cache_creation: Rate | None = None
