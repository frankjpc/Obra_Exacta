import pytest
from services.supabase_service import supabase_service
from services.session_manager import session_manager

def test_perfil_generation_and_demo():
    demo_id = "00000000-0000-0000-0000-000000000001"
    perfil = supabase_service.get_or_create_perfil(demo_id)
    assert perfil is not None
    assert perfil["user_id"] == demo_id
    assert perfil["codigo_vinculacion"] == "482910"
    assert "obx_mcp_" in perfil["api_key_mcp"]

def test_vincular_telegram_chat():
    test_user_id = "11111111-1111-1111-1111-111111111111"
    perfil = supabase_service.get_or_create_perfil(test_user_id)
    codigo = perfil["codigo_vinculacion"]
    assert len(codigo) == 6

    # Vinculación inválida
    assert supabase_service.vincular_telegram_chat("999999", 777888) is None

    # Vinculación válida
    vinculado = supabase_service.vincular_telegram_chat(codigo, 777888)
    assert vinculado is not None
    assert str(vinculado["telegram_chat_id"]) == "777888"

    # Búsqueda por chat_id
    encontrado = supabase_service.get_perfil_by_chat_id(777888)
    assert encontrado is not None
    assert encontrado["user_id"] == test_user_id

def test_multiuser_obra_isolation():
    user_a = "22222222-2222-2222-2222-222222222222"
    user_b = "33333333-3333-3333-3333-333333333333"

    obra_a = supabase_service.create_obra({
        "nombre": "Obra de Usuario A",
        "cliente": "Cliente A",
        "user_id": user_a
    }, user_id=user_a)

    obra_b = supabase_service.create_obra({
        "nombre": "Obra de Usuario B",
        "cliente": "Cliente B",
        "user_id": user_b
    }, user_id=user_b)

    obras_a = supabase_service.get_obras(user_id=user_a)
    ids_a = [o["id"] for o in obras_a]
    assert obra_a["id"] in ids_a
    assert obra_b["id"] not in ids_a

    obras_b = supabase_service.get_obras(user_id=user_b)
    ids_b = [o["id"] for o in obras_b]
    assert obra_b["id"] in ids_b
    assert obra_a["id"] not in ids_b

def test_session_manager_auto_links_user():
    chat_id = 999111
    user_c = "44444444-4444-4444-4444-444444444444"
    perfil = supabase_service.get_or_create_perfil(user_c)
    supabase_service.vincular_telegram_chat(perfil["codigo_vinculacion"], chat_id)

    # SessionManager resolve_context sin pasar user_id explícito
    ctx = session_manager.resolve_context(chat_id=chat_id, text="Cúbícame 10 m2 pared de bloque")
    assert ctx.obra is not None
    assert ctx.session_db.get("user_id") == user_c

def test_custom_price_user_filtering():
    user_x = "55555555-5555-5555-5555-555555555555"
    supabase_service.save_catalogo_precio({
        "clave_o_codigo": "cemento_premium",
        "nombre": "Cemento Premium",
        "precio_usd": 15.50
    }, user_id=user_x)

    precios_user = supabase_service.get_catalogo_precios_dict(user_id=user_x)
    assert precios_user.get("cemento_premium") == 15.50
