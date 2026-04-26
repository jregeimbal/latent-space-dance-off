"""
Configuration module for latent-space-dance-off.

Loads and manages application configuration from environment variables.
"""

import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Config(BaseModel):
    """Application configuration loaded from environment variables."""

    OLLAMA_HOST: str = Field(
        default="http://localhost:11434",
        description="Ollama API host URL"
    )
    NUM_JUDGES: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Number of models to act as judges"
    )
    OUTPUT_DIR: str = Field(
        default="./output",
        description="Output directory for SVGs and benchmarks"
    )
    MODEL_LIST: str = Field(
        default="",
        description="Comma-separated list of model names to benchmark"
    )
    NUM_THEMES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of SVG themes per model"
    )
    DEFAULT_CREATIVITY_WEIGHT: float = Field(
        default=0.33,
        ge=0,
        le=1,
        description="Weight for creativity score in final ranking"
    )
    DEFAULT_AESTHETICS_WEIGHT: float = Field(
        default=0.33,
        ge=0,
        le=1,
        description="Weight for aesthetics score in final ranking"
    )
    DEFAULT_COMPLEXITY_WEIGHT: float = Field(
        default=0.34,
        ge=0,
        le=1,
        description="Weight for complexity score in final ranking"
    )
    JUDGING_CRITERIA: str = Field(
        default="creativity,aesthetics,complexity",
        description="Comma-separated list of judging criteria"
    )

    model_config = ConfigDict()

    @field_validator('MODEL_LIST')
    @classmethod
    def parse_model_list(cls, v: str) -> str:
        """Parse MODEL_LIST, returning empty string if None."""
        if v is None:
            return ""
        return v

    @property
    def models(self) -> List[str]:
        """Parse MODEL_LIST into list of model names."""
        if not self.MODEL_LIST:
            return []
        return [m.strip() for m in self.MODEL_LIST.split(',') if m.strip()]

    @property
    def judging_criteria(self) -> List[str]:
        """Parse JUDGING_CRITERIA into list of criterion names."""
        if not self.JUDGING_CRITERIA:
            return ["creativity", "aesthetics", "complexity"]
        return [c.strip() for c in self.JUDGING_CRITERIA.split(',') if c.strip()]

    @property
    def svgs_dir(self) -> Path:
        """Get SVGs output directory."""
        return Path(self.OUTPUT_DIR) / "svgs"

    @property
    def benchmarks_dir(self) -> Path:
        """Get benchmarks output directory."""
        return Path(self.OUTPUT_DIR) / "benchmarks"

    @property
    def leaderboards_dir(self) -> Path:
        """Get leaderboards output directory."""
        return Path(self.OUTPUT_DIR) / "leaderboards"

    def output_path(self, filename: str) -> Path:
        """Join OUTPUT_DIR with filename, handling paths."""
        output_dir = Path(self.OUTPUT_DIR)
        return output_dir / filename

    def create_output_dirs(self) -> None:
        """Create output directories if they don't exist."""
        (Path(self.OUTPUT_DIR) / "svgs").mkdir(parents=True, exist_ok=True)
        (Path(self.OUTPUT_DIR) / "benchmarks").mkdir(parents=True, exist_ok=True)
        (Path(self.OUTPUT_DIR) / "leaderboards").mkdir(parents=True, exist_ok=True)

    def get_judge_count(self) -> int:
        """Return NUM_JUDGES as int with minimum of 1."""
        return max(1, int(self.NUM_JUDGES))

    def get_run_id_file(self) -> Path:
        """Get path to run_id tracking file."""
        return Path(self.OUTPUT_DIR) / "run_ids.txt"

    def __str__(self) -> str:
        """Return string representation of configuration."""
        return (
            f"Config(\n"
            f"  OLLAMA_HOST: {self.OLLAMA_HOST},\n"
            f"  NUM_JUDGES: {self.NUM_JUDGES},\n"
            f"  OUTPUT_DIR: {self.OUTPUT_DIR},\n"
            f"  NUM_THEMES: {self.NUM_THEMES},\n"
            f"  MODELS: {self.models}\n"
            f")"
        )


def get_config() -> Config:
    """Get Config instance, loading from environment if available.

    Returns:
        Config: Configuration instance
    """
    return Config()
