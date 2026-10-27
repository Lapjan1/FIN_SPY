"""
Registry loader - entity register bankcodes and deviations per bank
Loads config/banks.yaml and provides bank-specific parser config
Per user question: entity register bankcodes and deviations per bank
"""
from pathlib import Path
from typing import Dict, Optional
import yaml

_banks_config = None

def load_banks_config(path: str = "config/banks.yaml") -> Dict:
    global _banks_config
    if _banks_config is not None:
        return _banks_config
    p = Path(path)
    if not p.exists():
        # Try alternative path from project root
        p = Path(__file__).parent.parent.parent.parent / "config" / "banks.yaml"
    if not p.exists():
        p = Path("config/banks.yaml")
    if p.exists():
        with p.open() as f:
            _banks_config = yaml.safe_load(f)
            return _banks_config
    # Fallback minimal
    _banks_config = {"banks": {}, "entities": {}, "coa_seed": []}
    return _banks_config

def get_bank_config(bank_code: str) -> Optional[Dict]:
    cfg = load_banks_config()
    banks = cfg.get("banks", {})
    # Try exact match, then case-insensitive, then full name
    if bank_code in banks:
        return banks[bank_code]
    for k, v in banks.items():
        if k.lower() == bank_code.lower():
            return v
        if v.get("full_name", "").lower() == bank_code.lower():
            return v
    # Try by bankcode number
    for k, v in banks.items():
        if bank_code in v.get("bankcodes", []):
            return v
    return None

def get_all_banks() -> Dict:
    cfg = load_banks_config()
    return cfg.get("banks", {})

def get_coa_seed() -> list:
    cfg = load_banks_config()
    return cfg.get("coa_seed", [])

def get_entity_types() -> Dict:
    cfg = load_banks_config()
    return cfg.get("entities", {})

def detect_bank_from_text(text: str) -> Optional[str]:
    """
    Detect bank from text using keywords and bankcodes
    Returns bank key like FNB, STDB, etc.
    """
    cfg = load_banks_config()
    banks = cfg.get("banks", {})
    text_lower = text.lower()
    for bank_key, bank_cfg in banks.items():
        full_name = bank_cfg.get("full_name", "").lower()
        if bank_key.lower() in text_lower or full_name in text_lower:
            return bank_key
        for code in bank_cfg.get("bankcodes", []):
            if code in text:
                return bank_key
    return None
