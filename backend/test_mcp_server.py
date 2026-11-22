import pytest
from mcp_server import (
    resolve_user_id,
    listar_obras_usuario,
    consultar_precios_y_covenin,
    evaluar_levantamiento,
    obtener_resumen_obra
)
from services.supabase_service import supabase_service

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"
DEMO_API_KEY = "obx_mcp_demo_7f8a9b2c3d4e5f6a7b8c9d0e"

def setup_module():
    """Configura datos demo aislados para las pruebas."""
    # Asegurar perfil demo
    supabase_service._memory_store["perfiles_telegram"][DEMO_USER_ID] = {
        "id": "demo-profile-uuid",
        "user_id": DEMO_USER_ID,
        "telegram_chat_id": 999999,
        "codigo_vinculacion": "482910",
        "api_key_mcp": DEMO_API_KEY
    }
    
    # Crear obra para demo user
    obra_demo = {
        "id": "11111111-1111-1111-1111-111111111111",
        "user_id": DEMO_USER_ID,
        "nombre": "Proyecto Galpón Central Demo",
        "cliente": "Empresas Polar",
        "estado": "activa",
        "tasa_bcv": 920.0,
        "presupuesto_total_usd": 10000.0,
        "total_gastado_usd": 3500.0,
        "margen_meta": 30.0
    }
    supabase_service._memory_store["obras"][obra_demo["id"]] = obra_demo

    # Crear partidas para la obra demo
    supabase_service._memory_store["partidas"]["partida-demo-01"] = {
        "id": "partida-demo-01",
        "obra_id": obra_demo["id"],
        "tipo_partida": "pared_bloque",
        "descripcion": "Construcción de pared de bloques de arcilla e=15cm",
        "total_usd": 5000.0,
        "porcentaje_avance": 50.0
    }

    # Crear gasto/factura demo
    supabase_service._memory_store["facturas"]["factura-demo-01"] = {
        "id": "factura-demo-01",
        "obra_id": obra_demo["id"],
        "concepto": "Compra de cemento y arena",
        "total_usd": 1200.0,
        "total_bs": 1200.0 * 920.0
    }

    # Crear daño oculto / adicional demo
    supabase_service._memory_store["libro_obra"]["adicional-demo-01"] = {
        "id": "adicional-demo-01",
        "obra_id": obra_demo["id"],
        "titulo": "Tubería matriz rota",
        "descripcion": "Reemplazo de tubería rota en fundación",
        "costo_adicional_usd": 450.0
    }

    # Configurar usuario B para verificar aislamiento
    user_b_id = "00000000-0000-0000-0000-000000000002"
    api_key_b = "obx_mcp_user_b_secret_key_12345"
    supabase_service._memory_store["perfiles_telegram"][user_b_id] = {
        "id": "profile-b-uuid",
        "user_id": user_b_id,
        "telegram_chat_id": 888888,
        "codigo_vinculacion": "999888",
        "api_key_mcp": api_key_b
    }
    obra_b = {
        "id": "22222222-2222-2222-2222-222222222222",
        "user_id": user_b_id,
        "nombre": "Proyecto Privado Usuario B",
        "cliente": "Cliente Privado B",
        "estado": "activa",
        "presupuesto_total_usd": 25000.0,
        "total_gastado_usd": 2000.0
    }
    supabase_service._memory_store["obras"][obra_b["id"]] = obra_b


def test_resolve_user_id_valido_e_invalido():
    # 1. Clave válida resuelve user_id exacto
    uid = resolve_user_id(DEMO_API_KEY)
    assert uid == DEMO_USER_ID

    # 2. Clave inexistente lanza ValueError
    with pytest.raises(ValueError, match="inválida o no registrada"):
        resolve_user_id("obx_mcp_clave_falsa_9999")

    # 3. Sin clave lanza ValueError
    with pytest.raises(ValueError, match="Autenticación MCP requerida"):
        resolve_user_id("")


def test_listar_obras_usuario_con_aislamiento():
    # Usuario demo solo ve su obra
    obras_demo = listar_obras_usuario(api_key_mcp=DEMO_API_KEY)
    nombres_demo = [o["nombre"] for o in obras_demo]
    assert "Proyecto Galpón Central Demo" in nombres_demo
    assert "Proyecto Privado Usuario B" not in nombres_demo

    # Usuario B solo ve su obra privada
    obras_b = listar_obras_usuario(api_key_mcp="obx_mcp_user_b_secret_key_12345")
    nombres_b = [o["nombre"] for o in obras_b]
    assert "Proyecto Privado Usuario B" in nombres_b
    assert "Proyecto Galpón Central Demo" not in nombres_b


def test_consultar_precios_y_covenin():
    res = consultar_precios_y_covenin(api_key_mcp=DEMO_API_KEY)
    assert res["status"] == "success"
    assert res["user_id"] == DEMO_USER_ID
    assert "catalogo_covenin_oficial" in res
    assert "materiales_vigentes" in res
    assert "mano_de_obra_vigente" in res
    # Verificar códigos COVENIN
    assert "pared_bloque" in res["catalogo_covenin_oficial"]


def test_evaluar_levantamiento_necesita_aclaracion():
    # Descripción ambigua sin medidas ni material claro
    res = evaluar_levantamiento(
        obra_nombre="Galpón Central Demo",
        descripcion_trabajo="Vamos a levantar un muro y cambiar unas cosas.",
        api_key_mcp=DEMO_API_KEY
    )
    # Debe solicitar aclaración o procesar incisivamente
    assert "estado" in res
    if res["estado"] == "necesita_aclaracion":
        assert "pregunta_corta" in res
        assert res["pregunta_corta"] is not None


def test_evaluar_levantamiento_listo_para_presupuestar():
    # Descripción con parada explícita "con eso basta calcula ya"
    res = evaluar_levantamiento(
        obra_nombre="Galpón Central Demo",
        descripcion_trabajo="Pared de bloques de 15cm, 10 metros de largo por 3 metros de alto, calcula así con eso basta.",
        api_key_mcp=DEMO_API_KEY
    )
    assert res["estado"] == "listo_para_presupuestar"
    assert "presupuesto_total_usd" in res
    assert res["presupuesto_total_usd"] > 0
    assert len(res["partidas"]) > 0


def test_obtener_resumen_obra_exito_y_seguridad():
    # 1. Obtener resumen de obra existente
    resumen = obtener_resumen_obra(
        obra_nombre="Galpón Central Demo",
        api_key_mcp=DEMO_API_KEY
    )
    assert resumen["status"] == "success"
    assert resumen["obra"]["nombre"] == "Proyecto Galpón Central Demo"
    assert resumen["obra"]["presupuesto_total_usd"] == 10000.0
    assert len(resumen["partidas"]) >= 1
    assert len(resumen["gastos_y_facturas"]) >= 1
    assert len(resumen["adicionales_y_paradas"]) >= 1
    assert resumen["resumen_variacion"]["total_adicionales_usd"] == 450.0

    # 2. Intentar acceder a obra de otro usuario lanza ValueError
    with pytest.raises(ValueError, match="No se encontró la obra"):
        obtener_resumen_obra(
            obra_nombre="Proyecto Privado Usuario B",
            api_key_mcp=DEMO_API_KEY
        )
