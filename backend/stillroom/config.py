import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "stillroom.db"


def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    return Settings(
        data_dir=data_dir,
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    )
