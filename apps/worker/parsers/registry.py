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

def get_coa_templates() -> Dict:
    cfg = load_banks_config()
    return cfg.get("coa_templates", {})

def get_coa_template(template_name: str) -> Optional[Dict]:
    templates = get_coa_templates()
    return templates.get(template_name)

VALID_TEMPLATES = ("personal", "sme_cc", "mixed_sole_prop")

def get_active_template(tenant_id: str, db=None) -> str:
    """Return active template for tenant - we work with a choice on one of them at a time."""
    from apps.api.db import get_db as get_db_func
    if db is None:
        db = get_db_func()
    try:
        cur = db.execute("SELECT active_template FROM tenants WHERE id=?", (tenant_id,))
        row = cur.fetchone()
        if row:
            val = row["active_template"] if isinstance(row, dict) else row[0]
            if val in VALID_TEMPLATES:
                return val
    except Exception:
        pass
    return "personal"

def set_active_template(tenant_id: str, template: str, db=None) -> str:
    """Set active books choice for tenant. Validates template, seeds if needed, never works on non-existing accounts."""
    from apps.api.db import get_db as get_db_func
    if template not in VALID_TEMPLATES:
        raise ValueError(f"Invalid parameters: template must be one of {VALID_TEMPLATES}, got '{template}'")
    if db is None:
        db = get_db_func()
    # Ensure tenant exists
    cur = db.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,))
    if not cur.fetchone():
        raise ValueError(f"Invalid parameters: tenant '{tenant_id}' does not exist")
    seed_coa(tenant_id, template=template, db=db)
    db.execute("UPDATE tenants SET active_template=? WHERE id=?", (template, tenant_id))
    db.commit()
    return template

def ensure_coa_seeded(tenant_id: str, db=None) -> str:
    """Ensure the tenant row + active-template COA exist. Returns active template.

    Fresh tenants (upload -> suggest -> accept without opening books) get
    their default personal books seeded on first use instead of failing with
    'Seed COA first'. Only seeds the chosen template baseline - never creates
    per-suggestion accounts, so the suggester cannot invent codes.
    """
    from apps.api.db import get_db as get_db_func
    if db is None:
        db = get_db_func()
    try:
        cur = db.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,))
        if not cur.fetchone():
            db.execute(
                "INSERT INTO tenants (id, name, active_template) VALUES (?,?,?)",
                (tenant_id, f"Tenant {tenant_id}", "personal"),
            )
            db.commit()
    except Exception:
        pass
    active = get_active_template(tenant_id, db=db)
    try:
        # Sentinel must be a template row: extraction creates a bank ledger
        # row (same template, account_number set) before books are opened,
        # so a bare COUNT would mistake it for a seeded COA.
        cur = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND template=?"
            " AND code='9999' AND account_number IS NULL LIMIT 1",
            (tenant_id, active),
        )
        if not cur.fetchone():
            seed_coa(tenant_id, template=active, db=db)
    except Exception:
        pass
    return active


def seed_coa(tenant_id: str, template: str = "personal", db=None) -> int:
    """
    Seed COA for tenant from template per user choice: default personal and options mixed or business per merchant per account, for competition not lifetime project
    Template options: personal (default), sme_cc, mixed_sole_prop per config/banks.yaml coa_templates
    Returns number of accounts created. Only creates accounts for the chosen template.
    """
    from apps.api.db import get_db as get_db_func
    import uuid

    if template not in VALID_TEMPLATES:
        raise ValueError(f"Invalid parameters: template must be one of {VALID_TEMPLATES}, got '{template}'")

    if db is None:
        db = get_db_func()

    tmpl = get_coa_template(template)
    if not tmpl:
        # Fallback to generic coa_seed
        accounts = get_coa_seed()
        tmpl_accounts = [{"code": a.get("code"), "name": a.get("name"), "type": a.get("type")} for a in accounts]
    else:
        tmpl_accounts = tmpl.get("accounts", [])

    created = 0
    for acc in tmpl_accounts:
        code = acc.get("code")
        name = acc.get("name")
        type_ = acc.get("type", "expense")
        # Generate id acc-{tenant}-{template}-{code} so same code can exist in 3 books without collision
        acc_id = f"acc-{tenant_id}-{template}-{code}"
        # Check if exists for this template
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND code=? AND template=?", (tenant_id, code, template))
        if cur.fetchone():
            continue
        try:
            db.execute(
                "INSERT INTO accounts (id, tenant_id, code, name, type, template) VALUES (?,?,?,?,?,?)",
                (acc_id, tenant_id, code, name, type_, template)
            )
            created += 1
        except Exception as e:
            # If code exists or other error, skip
            pass
    # Set as active choice (one at a time)
    try:
        db.execute("UPDATE tenants SET active_template=? WHERE id=?", (template, tenant_id))
    except Exception:
        pass
    db.commit()
    return created

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
