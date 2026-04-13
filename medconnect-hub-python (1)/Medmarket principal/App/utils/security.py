import re
from functools import wraps
from flask import session, redirect, render_template
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """Return a secure hash of the given plaintext password."""
    return generate_password_hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True if *password* matches *stored_hash*."""
    return check_password_hash(stored_hash, password)


def sanitize_cpf(raw: str):
    """Strip non-digits and validate CPF length (11 digits).
    Returns the 11-digit string on success, or None when invalid.
    """
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 11 and digits.isdigit():
        return digits
    return None


def sanitize_cnpj(raw: str):
    """Strip non-digits and validate CNPJ length (14 digits).
    Returns the 14-digit string on success, or None when invalid.
    """
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 14 and digits.isdigit():
        return digits
    return None


def _current_user_type() -> str | None:
    """Return the user_type from the active session, or None."""
    return (session.get("user") or {}).get("user_type")


def login_required(f):
    """Redirect to /auth (preserving the current path) if no user is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            from flask import request as _req
            next_url = _req.url
            return redirect(f"/auth?redirect={next_url}")
        return f(*args, **kwargs)
    return decorated


def login_required_patient(f):
    """Protect patient-only routes:
    - Not logged in        → redirect to /auth (with ?redirect)
    - Logged in as CLINICA → redirect back with ?aviso=clinic_blocked
    - Logged in as CLIENTE → allow
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request as _req
        user = session.get("user")
        if not user:
            return redirect(f"/auth?redirect={_req.url}")
        if user.get("user_type") == "CLINICA":
            # Safely extract the listing_id from the path to redirect back
            listing_id = kwargs.get("listing_id") or kwargs.get("listing") or ""
            if listing_id:
                return redirect(f"/listing/{listing_id}?aviso=clinic_blocked")
            return render_template("403.html"), 403
        return f(*args, **kwargs)
    return decorated


def login_required_clinic(f):
    """Protect clinic routes:
    - Not logged in          → redirect to /clinica/login
    - Logged in as CLIENTE   → 403 Acesso Negado
    - Logged in as CLINICA   → allow
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        if not user:
            return redirect("/clinica/login")
        if user.get("user_type") != "CLINICA":
            return render_template("403.html"), 403
        return f(*args, **kwargs)
    return decorated


# Keep alias so any legacy import still works
clinic_required = login_required_clinic