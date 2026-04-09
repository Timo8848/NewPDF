from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class OCRSettings(BaseModel):
    tesseract_cmd: str = Field(default="tesseract", description="Path to tesseract binary")
    languages: list[str] = Field(default_factory=lambda: ["eng"], description="Language packs")
    dpi: int = 300


class ValidationSettings(BaseModel):
    enforce_totals: bool = True
    enforce_dates: bool = True
    total_tolerance: str = "0.02"  # Decimal-compatible string
    min_confidence: float = 0.4


class StorageSettings(BaseModel):
    duckdb_path: Path = Field(default=Path("data/idp.duckdb"))


class ServiceSettings(BaseModel):
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    enable_metrics: bool = True


class Settings(BaseModel):
    ocr: OCRSettings = OCRSettings()
    validation: ValidationSettings = ValidationSettings()
    storage: StorageSettings = StorageSettings()
    service: ServiceSettings = ServiceSettings()
    schema_path: Path = Path("src/idp/config/schema.yaml")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
