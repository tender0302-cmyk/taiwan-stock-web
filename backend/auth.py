# =============================================
#  認證模組 — JWT + 白名單帳號
# =============================================

import os, hashlib, hmac, base64, json, time
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import get_conn

router  = APIRouter()
bearer  = HTTPBearer()

SECRET  = os.environ.get("JWT_SECRET", "your-super-secret-key-change-this")
EXPIRE  = 60 * 60 * 24 * 7   # 7天

# ── JWT（輕量自製，不依賴第三方）──────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _sign(payload: dict) -> str:
    header  = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body    = _b64(json.dumps(payload).encode())
    sig     = hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(sig)}"

def _verify(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError
        header, body, sig = parts
        expected = _b64(hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        if payload.get("exp", 0) < time.time():
            raise ValueError("expired")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token 無效或已過期")

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    return _verify(creds.credentials)

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理員權限")
    return user

# ── Routes ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/login")
def login(req: LoginRequest):
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM users WHERE username=?", (req.username,)
    ).fetchone()
    conn.close()

    if not row or row["password"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    token = _sign({
        "sub":      row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "exp":      int(time.time()) + EXPIRE,
    })
    return {"token": token, "username": row["username"], "is_admin": bool(row["is_admin"])}

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user

@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM users WHERE id=?", (user["sub"],)).fetchone()
    if row["password"] != hash_password(req.old_password):
        conn.close()
        raise HTTPException(status_code=400, detail="舊密碼錯誤")
    conn.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(req.new_password), user["sub"])
    )
    conn.commit()
    conn.close()
    return {"message": "密碼修改成功"}

# ── 管理員：管理白名單帳號 ─────────────────────────────────────

@router.get("/users")
def list_users(admin: dict = Depends(require_admin)):
    conn  = get_conn()
    rows  = conn.execute("SELECT id, username, is_admin, created_at FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/users")
def create_user(req: RegisterRequest, admin: dict = Depends(require_admin)):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (req.username, hash_password(req.password))
        )
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="帳號已存在")
    conn.close()
    return {"message": f"帳號 {req.username} 建立成功"}

@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="不能刪除自己")
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "帳號已刪除"}
