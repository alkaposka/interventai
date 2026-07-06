import pytest
from fastapi.testclient import TestClient
from app import app, init_db, db_query

init_db()
client = TestClient(app)

def get_auth_headers():
    res = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}

def test_register_contract_valid():
    h = get_auth_headers()
    db_query("DELETE FROM contratos WHERE numero = ?", ("C-2026-999",), commit=True)
    data = {"numero": "C-2026-999", "objeto": "Auditoría de pruebas QA", "contratista": "QA Testing SAS", "fecha_inicio": "2026-07-01", "fecha_fin": "2026-12-31", "valor_total": 50000000.0, "estado": "Activo", "interventor_ids": [1]}
    res = client.post("/contratos", json=data, headers=h)
    assert res.status_code == 201 and res.json()["success"] is True and "id" in res.json()

def test_register_contract_missing_fields():
    h = get_auth_headers()
    assert client.post("/contratos", json={"contratista": "Test Ltd", "valor_total": 10.0}, headers=h).status_code == 422

def test_change_contract_state_tracking():
    h = get_auth_headers()
    data = {"estado": "Suspendido", "porcentaje_avance": 42.5, "saldo_financiero": 85000000.0, "notas": "Clima", "fecha": "2026-07-06"}
    assert client.put("/seguimiento/1", json=data, headers=h).status_code == 200
    check = client.get("/contratos/1", headers=h)
    assert check.status_code == 200 and check.json()["estado"] == "Suspendido"

def test_update_contract_metadata():
    h = get_auth_headers()
    data = {"numero": "C-2026-002-EDITED", "objeto": "Editado", "contratista": "Tech Solutions", "fecha_inicio": "2026-02-15", "fecha_fin": "2026-10-15", "valor_total": 95000000.0, "estado": "Activo", "interventor_ids": [2]}
    assert client.put("/contratos/2", json=data, headers=h).status_code == 200
    check = client.get("/contratos/2", headers=h)
    assert check.status_code == 200 and check.json()["numero"] == "C-2026-002-EDITED" and check.json()["valor_total"] == 95000000.0

def test_generate_report():
    h = get_auth_headers()
    res = client.get("/reportes", headers=h)
    assert res.status_code == 200 and "totals" in res.json() and "items" in res.json()

def test_get_audit_logs():
    h = get_auth_headers()
    res = client.get("/audit-logs", headers=h)
    assert res.status_code == 200 and len(res.json()) > 0
    actions = [l["accion"] for l in res.json()]
    assert "UPDATE" in actions or "CREATE" in actions

def test_delete_contract():
    h = get_auth_headers()
    assert client.delete("/contratos/3", headers=h).status_code == 200
    assert client.get("/contratos/3", headers=h).status_code == 404
