import os
import sqlite3
import bcrypt
import time
import hmac
import hashlib
import json
import base64
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

DB_FILE = "interventai.db"
SECRET_KEY = "interventorai_super_secret_key"

app = FastAPI(title="InterventorAI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom JWT Helpers
def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + '=' * (4 - (len(data) % 4)))

def create_jwt(payload: dict) -> str:
    msg = f"{base64url_encode(json.dumps({'alg':'HS256','typ':'JWT'}).encode())}.{base64url_encode(json.dumps(payload).encode())}"
    sig = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()
    return f"{msg}.{base64url_encode(sig)}"

def verify_jwt(token: str) -> dict | None:
    try:
        parts = token.split('.')
        msg = f"{parts[0]}.{parts[1]}"
        sig = hmac.new(SECRET_KEY.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()
        if not hmac.compare_digest(base64url_decode(parts[2]), sig):
            return None
        payload = json.loads(base64url_decode(parts[1]).decode('utf-8'))
        return payload if payload.get("exp", 0) > time.time() else None
    except Exception:
        return None

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorización faltante")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Formato de token inválido")
    payload = verify_jwt(parts[1])
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return payload

# DB Helper
def db_query(q: str, p: tuple = (), one: bool = False, commit: bool = False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute(q, p)
    if commit:
        conn.commit()
        last_id = cur.lastrowid
        conn.close()
        return last_id
    res = cur.fetchone() if one else cur.fetchall()
    conn.close()
    return dict(res) if one and res else ([dict(r) for r in res] if not one else None)

def log_audit(user_id: int, table: str, reg_id: int, action: str):
    db_query("INSERT INTO audit_logs (usuario_id, tabla, registro_id, accion, timestamp) VALUES (?, ?, ?, ?, ?)",
             (user_id, table, reg_id, action, time.strftime("%Y-%m-%d %H:%M:%S")), commit=True)

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class ContractCreate(BaseModel):
    numero: str
    objeto: str
    contratista: str
    fecha_inicio: str
    fecha_fin: str
    valor_total: float
    estado: str = "Activo"
    interventor_ids: List[int] = []

class InterventorCreate(BaseModel):
    identificacion: str
    nombre: str
    email: str
    profesion: str

class ActaCreate(BaseModel):
    contrato_id: int
    interventor_id: int
    fecha: str
    descripcion: str
    porcentaje_avance: float

class SeguimientoUpdate(BaseModel):
    estado: str
    porcentaje_avance: float
    saldo_financiero: float
    notas: str
    fecha: str

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin');
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT UNIQUE NOT NULL, objeto TEXT NOT NULL, contratista TEXT NOT NULL, fecha_inicio TEXT NOT NULL, fecha_fin TEXT NOT NULL, valor_total REAL NOT NULL, estado TEXT NOT NULL DEFAULT 'Activo');
    CREATE TABLE IF NOT EXISTS interventores (id INTEGER PRIMARY KEY AUTOINCREMENT, identificacion TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, email TEXT UNIQUE NOT NULL, profesion TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS contratos_interventores (contrato_id INTEGER, interventor_id INTEGER, PRIMARY KEY (contrato_id, interventor_id), FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE, FOREIGN KEY (interventor_id) REFERENCES interventores(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS actas (id INTEGER PRIMARY KEY AUTOINCREMENT, contrato_id INTEGER NOT NULL, interventor_id INTEGER NOT NULL, fecha TEXT NOT NULL, descripcion TEXT NOT NULL, porcentaje_avance REAL NOT NULL, FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE, FOREIGN KEY (interventor_id) REFERENCES interventores(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS seguimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, contrato_id INTEGER NOT NULL, fecha TEXT NOT NULL, notas TEXT NOT NULL, porcentaje_avance REAL NOT NULL, saldo_financiero REAL NOT NULL, FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, tabla TEXT NOT NULL, registro_id INTEGER NOT NULL, accion TEXT NOT NULL, timestamp TEXT NOT NULL, FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL);
    """)
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        h = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode('utf-8')
        cur.execute("INSERT INTO usuarios (username, password_hash, role) VALUES ('admin', ?, 'admin'), ('jessica', ?, 'admin'), ('janeth', ?, 'admin')", (h, h, h))
        cur.executescript("""
        INSERT INTO interventores (identificacion, nombre, email, profesion) VALUES 
        ('1012345678', 'Carlos Mendoza', 'carlos.mendoza@email.com', 'Ingeniero Civil'),
        ('1087654321', 'Diana Patricia Gómez', 'diana.gomez@email.com', 'Ingeniera de Sistemas');
        INSERT INTO contratos (numero, objeto, contratista, fecha_inicio, fecha_fin, valor_total, estado) VALUES
        ('C-2026-001', 'Supervisión de obras viales fase 1', 'Consorcio Vial 2026', '2026-01-01', '2026-12-31', 150000000.0, 'Activo'),
        ('C-2026-002', 'Interventoría al desarrollo de software InterventorAI', 'Tech Solutions SAS', '2026-02-15', '2026-08-15', 80000000.0, 'Activo'),
        ('C-2026-003', 'Auditoría ambiental cuenca del río Bogotá', 'EcoConsultores Ltda', '2026-03-01', '2026-09-01', 45000000.0, 'Suspendido');
        INSERT INTO contratos_interventores (contrato_id, interventor_id) VALUES (1, 1), (2, 2), (3, 2);
        INSERT INTO actas (contrato_id, interventor_id, fecha, descripcion, porcentaje_avance) VALUES (1, 1, '2026-03-01', 'Primera revisión de diseños y plan de obras', 20.0);
        INSERT INTO seguimientos (contrato_id, fecha, notas, porcentaje_avance, saldo_financiero) VALUES (1, '2026-04-01', 'Avance de obra física según cronograma', 35.0, 110000000.0);
        """)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/", response_class=HTMLResponse)
def read_root():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Frontend index.html not found in static/</h3>"

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/auth/login")
@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db_query("SELECT * FROM usuarios WHERE username = ?", (req.username.lower(),), one=True)
    if not user or not bcrypt.checkpw(req.password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {
        "token": create_jwt({"id": user["id"], "sub": user["username"], "role": user["role"], "exp": time.time() + 86400}),
        "user": {"username": user["username"], "role": user["role"]}
    }

@app.get("/contratos")
@app.get("/api/contratos")
def get_contratos(u: dict = Depends(get_current_user)):
    contratos = db_query("SELECT * FROM contratos")
    for c in contratos:
        c["interventores"] = db_query("SELECT i.* FROM interventores i JOIN contratos_interventores ci ON i.id = ci.interventor_id WHERE ci.contrato_id = ?", (c["id"],))
        latest = db_query("SELECT porcentaje_avance, saldo_financiero FROM seguimientos WHERE contrato_id = ? ORDER BY id DESC LIMIT 1", (c["id"],), one=True)
        c["porcentaje_avance"] = latest["porcentaje_avance"] if latest else 0.0
        c["saldo_financiero"] = latest["saldo_financiero"] if latest else c["valor_total"]
    return contratos

@app.post("/contratos", status_code=201)
@app.post("/api/contratos", status_code=201)
def create_contrato(req: ContractCreate, u: dict = Depends(get_current_user)):
    try:
        c_id = db_query("INSERT INTO contratos (numero, objeto, contratista, fecha_inicio, fecha_fin, valor_total, estado) VALUES (?, ?, ?, ?, ?, ?, ?)", (req.numero, req.objeto, req.contratista, req.fecha_inicio, req.fecha_fin, req.valor_total, req.estado), commit=True)
        for i_id in req.interventor_ids:
            db_query("INSERT INTO contratos_interventores (contrato_id, interventor_id) VALUES (?, ?)", (c_id, i_id), commit=True)
        log_audit(u.get("id"), "contratos", c_id, "CREATE")
        return {"success": True, "id": c_id}
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Error de integridad: {str(e)}")

@app.get("/contratos/{id}")
@app.get("/api/contratos/{id}")
def get_contrato(id: int, u: dict = Depends(get_current_user)):
    c = db_query("SELECT * FROM contratos WHERE id = ?", (id,), one=True)
    if not c:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    c["interventores"] = db_query("SELECT i.* FROM interventores i JOIN contratos_interventores ci ON i.id = ci.interventor_id WHERE ci.contrato_id = ?", (id,))
    c["actas"] = db_query("SELECT * FROM actas WHERE contrato_id = ? ORDER BY fecha DESC", (id,))
    c["seguimientos"] = db_query("SELECT * FROM seguimientos WHERE contrato_id = ? ORDER BY id DESC", (id,))
    c["porcentaje_avance"] = c["seguimientos"][0]["porcentaje_avance"] if c["seguimientos"] else 0.0
    c["saldo_financiero"] = c["seguimientos"][0]["saldo_financiero"] if c["seguimientos"] else c["valor_total"]
    return c

@app.put("/contratos/{id}")
@app.put("/api/contratos/{id}")
def update_contrato(id: int, req: ContractCreate, u: dict = Depends(get_current_user)):
    if not db_query("SELECT id FROM contratos WHERE id = ?", (id,), one=True):
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    db_query("""
        UPDATE contratos 
        SET numero = ?, objeto = ?, contratista = ?, fecha_inicio = ?, fecha_fin = ?, valor_total = ?, estado = ? 
        WHERE id = ?
    """, (req.numero, req.objeto, req.contratista, req.fecha_inicio, req.fecha_fin, req.valor_total, req.estado, id), commit=True)
    db_query("DELETE FROM contratos_interventores WHERE contrato_id = ?", (id,), commit=True)
    for i_id in req.interventor_ids:
        db_query("INSERT INTO contratos_interventores (contrato_id, interventor_id) VALUES (?, ?)", (id, i_id), commit=True)
    log_audit(u.get("id"), "contratos", id, "UPDATE")
    return {"success": True}

@app.delete("/contratos/{id}")
@app.delete("/api/contratos/{id}")
def delete_contrato(id: int, u: dict = Depends(get_current_user)):
    if not db_query("SELECT id FROM contratos WHERE id = ?", (id,), one=True):
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    db_query("DELETE FROM contratos WHERE id = ?", (id,), commit=True)
    log_audit(u.get("id"), "contratos", id, "DELETE")
    return {"success": True}

@app.post("/actas")
@app.post("/api/actas")
def create_acta(req: ActaCreate, u: dict = Depends(get_current_user)):
    try:
        a_id = db_query("INSERT INTO actas (contrato_id, interventor_id, fecha, descripcion, porcentaje_avance) VALUES (?, ?, ?, ?, ?)", (req.contrato_id, req.interventor_id, req.fecha, req.descripcion, req.porcentaje_avance), commit=True)
        log_audit(u.get("id"), "actas", a_id, "CREATE")
        return {"success": True, "id": a_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/actas")
@app.get("/api/actas")
def get_actas(u: dict = Depends(get_current_user)):
    return db_query("SELECT a.*, c.numero as contrato_numero, i.nombre as interventor_nombre FROM actas a JOIN contratos c ON a.contrato_id = c.id JOIN interventores i ON a.interventor_id = i.id ORDER BY a.fecha DESC")

@app.put("/seguimiento/{id}")
@app.put("/api/seguimiento/{id}")
def update_seguimiento(id: int, req: SeguimientoUpdate, u: dict = Depends(get_current_user)):
    if not db_query("SELECT id FROM contratos WHERE id = ?", (id,), one=True):
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    db_query("UPDATE contratos SET estado = ? WHERE id = ?", (req.estado, id), commit=True)
    s_id = db_query("INSERT INTO seguimientos (contrato_id, fecha, notas, porcentaje_avance, saldo_financiero) VALUES (?, ?, ?, ?, ?)", (id, req.fecha, req.notas, req.porcentaje_avance, req.saldo_financiero), commit=True)
    log_audit(u.get("id"), "seguimientos", s_id, "CREATE")
    return {"success": True}

@app.get("/reportes")
@app.get("/api/reportes")
def get_reportes(u: dict = Depends(get_current_user)):
    contratos = db_query("SELECT id, numero, objeto, contratista, valor_total, estado FROM contratos")
    total_presupuesto, total_ejecutado, items = 0.0, 0.0, []
    for c in contratos:
        latest = db_query("SELECT porcentaje_avance, saldo_financiero FROM seguimientos WHERE contrato_id = ? ORDER BY id DESC LIMIT 1", (c["id"],), one=True)
        progreso = latest["porcentaje_avance"] if latest else 0.0
        saldo = latest["saldo_financiero"] if latest else c["valor_total"]
        ejecutado = c["valor_total"] - saldo
        total_presupuesto += c["valor_total"]
        total_ejecutado += ejecutado
        names = [r["nombre"] for r in db_query("SELECT i.nombre FROM interventores i JOIN contratos_interventores ci ON i.id = ci.interventor_id WHERE ci.contrato_id = ?", (c["id"],))]
        items.append({"contrato": c["numero"], "objeto": c["objeto"], "contratista": c["contratista"], "estado": c["estado"], "progreso": progreso, "saldo": saldo, "interventores": names})
    return {"totals": {"presupuesto": total_presupuesto, "ejecutado": total_ejecutado}, "items": items}

@app.get("/audit-logs")
@app.get("/api/audit-logs")
def get_audit_logs(u: dict = Depends(get_current_user)):
    return db_query("SELECT a.*, u.username as usuario FROM audit_logs a LEFT JOIN usuarios u ON a.usuario_id = u.id ORDER BY a.id DESC")

@app.get("/interventores")
@app.get("/api/interventores")
def get_interventores(u: dict = Depends(get_current_user)):
    return db_query("SELECT * FROM interventores")

@app.post("/interventores", status_code=201)
@app.post("/api/interventores", status_code=201)
def create_interventor(req: InterventorCreate, u: dict = Depends(get_current_user)):
    try:
        i_id = db_query("INSERT INTO interventores (identificacion, nombre, email, profesion) VALUES (?, ?, ?, ?)", (req.identificacion, req.nombre, req.email, req.profesion), commit=True)
        return {"success": True, "id": i_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Identificación o correo duplicados")
