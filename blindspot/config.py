from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    model: str = "muse-spark-1.3"
    base_url: str = "https://api.meta.ai/v1"
    temperature: float = 1.0
    reasoning_effort: str = "low"
    max_completion_tokens: int = 4096
    timeout: float = 120
    retries: int = 2
    trials: int = 5
    concurrency: int = 3
    db_path: str = str(ROOT / "var" / "blindspot.sqlite3")
    force_mock: bool = False
    seed_demo: bool = True
    bank_path: str | None = None

    @property
    def mode(self):
        return "mock" if self.force_mock or not self.api_key else "live"

    @property
    def namespace(self):
        return "mock-v1" if self.mode == "mock" else hashlib.sha256(self.api_key.encode()).hexdigest()[:16]

    def public(self):
        return dict(mode=self.mode, model=self.model, temperature=self.temperature,
                    reasoning_effort=self.reasoning_effort, max_completion_tokens=self.max_completion_tokens,
                    trials=self.trials, concurrency=self.concurrency,
                    endpoint=self.base_url.rstrip("/") + "/chat/completions")


def load_settings():
    load_dotenv(ROOT / ".env", override=False)
    db = Path(os.getenv("BLINDSPOT_DB", "var/blindspot.sqlite3"))
    s = Settings(api_key=os.getenv("META_API_KEY", "").strip(), model=os.getenv("META_MODEL", "muse-spark-1.3"),
                 base_url=os.getenv("META_BASE_URL", "https://api.meta.ai/v1"),
                 temperature=float(os.getenv("META_TEMPERATURE", "1.0")),
                 reasoning_effort=os.getenv("META_REASONING_EFFORT", "low"),
                 max_completion_tokens=int(os.getenv("META_MAX_COMPLETION_TOKENS", "4096")),
                 timeout=float(os.getenv("META_TIMEOUT_SECONDS", "120")), retries=int(os.getenv("META_MAX_RETRIES", "2")),
                 trials=int(os.getenv("BLINDSPOT_TRIALS", "5")), concurrency=int(os.getenv("BLINDSPOT_CONCURRENCY", "3")),
                 db_path=str(db if db.is_absolute() else ROOT / db),
                 force_mock=os.getenv("BLINDSPOT_MOCK", "false").lower() == "true",
                 seed_demo=os.getenv("BLINDSPOT_SEED_DEMO", "true").lower() == "true")
    if os.getenv('BLINDSPOT_BANK'):
        bank = Path(os.environ['BLINDSPOT_BANK'])
        s = replace(s, bank_path=str(bank if bank.is_absolute() else ROOT / bank))
    if not 0 <= s.temperature <= 2 or not 1 <= s.trials <= 30 or not 1 <= s.concurrency <= 8:
        raise ValueError("Temperature must be 0–2; trials 1–30; concurrency 1–8.")
    if s.reasoning_effort not in {"minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Unsupported META_REASONING_EFFORT.")
    if s.reasoning_effort=='max' and s.model not in {'muse-spark-1.3','muse-wonder-1.0'}:
        raise ValueError('Max reasoning requires Standard Spark 1.3 or Muse Wonder.')
    if not 256 <= s.max_completion_tokens <= 32768 or s.timeout <= 0 or not 0 <= s.retries <= 5:
        raise ValueError("Invalid token limit, timeout or retry count.")
    if s.mode == "live" and not s.base_url.startswith("https://"):
        raise ValueError("Live Meta endpoint must use HTTPS.")
    return s
