from fastapi.testclient import TestClient
from main import app
from config import settings
from services.supabase_service import supabase_service

def test_api_full_workflow():
    client = TestClient(app)

    # 1. Status del sistema y Tasa Oficial BCV
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    st_json = res_status.json()
    assert st_json["status"] == "online"
    assert "telegram_bot_status" in st_json

    res_bcv = client.get("/api/bcv")
    assert res_bcv.status_code == 200
    bcv_json = res_bcv.json()
    assert "tasa_bcv" in bcv_json
    assert bcv_json["tasa_bcv"] > 0

    # 2. Seed de obra demo
    res_seed = client.post("/api/seed-demo")
    assert res_seed.status_code == 200
    seed_json = res_seed.json()
    assert seed_json["status"] == "ok"
    obra_id = seed_json["obra_id"]

    # 3. Listar obras y verificar obra demo
    res_obras = client.get("/api/obras")
    assert res_obras.status_code == 200
    obras = res_obras.json()
    assert len(obras) > 0
    obra = next(o for o in obras if o["id"] == obra_id)
    assert obra["tasa_bcv"] == settings.TASA_BCV_DEFAULT

    # 4. Listar partidas tabuladas 2D
    res_partidas = client.get(f"/api/obras/{obra_id}/partidas")
    assert res_partidas.status_code == 200
    partidas = res_partidas.json()
    assert len(partidas) >= 5

    # Verificar existencia de 6 columnas
    p1 = partidas[0]
    for col in ["descripcion", "unidad", "p_unit_usd", "total_usd", "p_unit_bs", "total_bs"]:
        assert col in p1, f"Falta columna {col} en partida"

    # 5. Probar endpoint de levantamiento por texto (Respaldo Web Total)
    payload_lev = {
        "obra_id": obra_id,
        "texto": "Pared de bloque de 8 metros de largo por 2.80 de alto, friso dos caras, y 40 metros cuadrados de pintura",
        "tasa_bcv": 68.50
    }
    res_lev = client.post("/api/levantamiento/texto", json=payload_lev)
    assert res_lev.status_code == 200
    lev_json = res_lev.json()
    assert lev_json["status"] == "success"
    assert len(lev_json["presupuesto"]["partidas"]) >= 2

    # 6. Probar subida de factura
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), color="white").save(buf, format="JPEG")
    fake_img = buf.getvalue()
    files = {"factura_img": ("factura_test.jpg", fake_img, "image/jpeg")}
    data = {"obra_id": obra_id}

    res_fac1 = client.post("/api/facturas/upload", data=data, files=files)
    assert res_fac1.status_code == 200
    fac1_json = res_fac1.json()
    assert fac1_json["status"] in ("success", "error_unreadable", "error_duplicate")

    # Registrar el hash para probar duplicado SHA-256
    from services.invoice_service import invoice_service
    opt_bytes, _ = invoice_service.optimize_image(fake_img)
    test_hash = invoice_service.compute_sha256(opt_bytes)
    supabase_service.save_factura({
        "obra_id": obra_id,
        "proveedor": "Ferretería Test C.A.",
        "nro_control": "FAC-TEST-001",
        "fecha": "2026-11-21",
        "total_usd": 50.0,
        "total_bs": 45938.5,
        "hash_sha256": test_hash
    })

    # Segunda subida idéntica: debe detectar duplicado SHA-256
    files_dup = {"factura_img": ("factura_test_copy.jpg", fake_img, "image/jpeg")}
    res_fac_dup = client.post("/api/facturas/upload", data=data, files=files_dup)
    assert res_fac_dup.status_code == 200
    fac_dup_json = res_fac_dup.json()
    assert fac_dup_json["status"] == "error_duplicate"
    assert fac_dup_json["alerta_duplicada"] is True
    assert "DUPLICADA" in fac_dup_json["detalle_alerta"]

    # 7. Probar flujo de aprobación de daño oculto / libro de obra
    incidencias = client.get(f"/api/obras/{obra_id}/libro-obra").json()
    assert len(incidencias) > 0
    token = incidencias[0]["token_aprobacion"]

    # Consultar endpoint de cliente público
    res_token = client.get(f"/api/aprobar/{token}")
    assert res_token.status_code == 200
    token_json = res_token.json()
    assert "incidencia" in token_json
    assert "costo_adicional_usd" in token_json["incidencia"]

    # Ejecutar aprobación por el cliente
    res_aprob = client.post(f"/api/aprobar/{token}", json={"cliente_nombre": "Ing. Carlos Mendoza (Cliente)"})
    assert res_aprob.status_code == 200
    aprob_json = res_aprob.json()
    assert aprob_json["status"] == "success"
    assert aprob_json["incidencia"]["estado_aprobacion"] == "aprobado"
    assert aprob_json["incidencia"]["cliente_nombre"] == "Ing. Carlos Mendoza (Cliente)"

    # 8. Probar flujo de avance de la cuadrilla (Telegram / Campo)
    from services.site_log_service import site_log_service
    res_cuadrilla = site_log_service.process_progress_or_incident(
        obra_id=obra_id,
        text_or_audio="Terminamos la colocación de cerámica en piso al 95%",
        responsable_nombre="Cuadrilla de Acabados (Maestro José)"
    )
    assert res_cuadrilla["tipo"] == "avance_obra"
    assert res_cuadrilla["porcentaje"] == 95.0
    assert "AVANCE DE CUADRILLA" in res_cuadrilla["mensaje"]
    assert res_cuadrilla["avance_global"] > 0

    print("¡Integración de API REST, Cálculos y Flujos completada al 100%!")

if __name__ == "__main__":
    test_api_full_workflow()
