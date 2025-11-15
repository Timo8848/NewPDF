from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class OCRSettings(BaseModel):
    tesseract_cmd: str = Field(default="tesseract", description="Path to tesseract binary")
    languages: list[str] = Field(default_factory=lambda: ["eng"], description="Language packs")
    dpi: int = 300
    enable_psm_auto: bool = True
    cache_dir: Path = Field(default=Path(".cache/ocr"))


class LayoutModelSettings(BaseModel):
    provider: Literal["layoutlmv3", "doctr"] = "layoutlmv3"
    model_name: str = "microsoft/layoutlmv3-base"
    max_seq_length: int = 512
    device: Literal["cpu", "cuda"] = "cpu"
    confidence_threshold: float = 0.5


class ValidationSettings(BaseModel):
    enforce_totals: bool = True
    enforce_dates: bool = True
    min_confidence: float = 0.4


class StorageSettings(BaseModel):
    temp_dir: Path = Field(default=Path("/tmp/idp"))
    duckdb_path: Path = Field(default=Path("data/idp.duckdb"))


class ServiceSettings(BaseModel):
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    enable_tracing: bool = False
    enable_metrics: bool = True


class Settings(BaseModel):
    ocr: OCRSettings = OCRSettings()
    layout: LayoutModelSettings = LayoutModelSettings()
    validation: ValidationSettings = ValidationSettings()
    storage: StorageSettings = StorageSettings()
    service: ServiceSettings = ServiceSettings()
    schema_path: Path = Path("src/idp/config/schema.yaml")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
