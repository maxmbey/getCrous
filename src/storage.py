import json
from pathlib import Path
from typing import Dict, Any

DATA_FILE = Path("data.json")


def load_data() -> Dict[str, Any]:
    """Charge le JSON (ou crée une structure vide si absent)."""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"accommodations": {}}


def save_data(data: Dict[str, Any]) -> None:
    """Sauvegarde le JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)