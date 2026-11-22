from services.session_manager import session_manager
from services.supabase_service import supabase_service
from services.levantamiento_skill import levantamiento_skill

def test_session_manager_esperando_aclaracion():
    chat_id = "55512345"
    session_manager.clear_chat_sessions(chat_id)
    levantamiento_skill.clear_session(int(chat_id))

    # Crear una obra y una sesión en estado 'esperando_aclaracion'
    obra = supabase_service.create_obra({
        "nombre": "Proyecto Espera",
        "cliente": "Cliente Test",
        "estado": "activa",
        "telegram_chat_id": int(chat_id)
    })

    sesion_data = session_manager.create_session(
        telegram_chat_id=chat_id,
        obra_id=obra["id"],
        obra_nombre=obra["nombre"],
        estado="esperando_aclaracion"
    )

    # Actualizar con una pregunta previa
    session_manager.save_session_state(
        chat_id=chat_id,
        session_id=sesion_data["id"],
        obra_id=obra["id"],
        obra_nombre=obra["nombre"],
        estado="esperando_aclaracion",
        rondas_preguntas=1,
        borrador_json={"obra_nombre": obra["nombre"], "partidas": [{"tipo_partida": "pared_bloque", "descripcion": "pared 6x2.80", "largo": 6.0, "alto": 2.80, "cantidad": 1.0, "area": 16.8, "unidad": "m2"}]},
        user_msg="pared 6x2.80",
        bot_msg="¿Es bloque de 15 o de 10cm?"
    )

    # Resolver contexto con la respuesta del usuario
    res = session_manager.resolve_context(chat_id=chat_id, text="es de 15cm")
    
    # REGLA 4: Debe asumir que el mensaje es la respuesta a la pregunta anterior del loop
    assert res.accion == "respuesta_aclaracion"
    assert res.obra["id"] == obra["id"]
    assert res.session_db["estado"] == "esperando_aclaracion"
    assert len(res.session_db["historial_mensajes"]) == 2

def test_session_manager_retoma_obra_existente():
    chat_id = "55567890"
    session_manager.clear_chat_sessions(chat_id)

    # Crear obra de prueba previa
    obra_planta = supabase_service.create_obra({
        "nombre": "Planta Cagua Industrial",
        "cliente": "Empresas Polar",
        "estado": "pausada",
        "telegram_chat_id": int(chat_id)
    })

    # El usuario menciona explícitamente la planta
    res = session_manager.resolve_context(
        chat_id=chat_id,
        text="Sobre la obra de la planta necesitamos 50 m2 de pintura"
    )

    assert res.accion == "retoma_obra"
    assert res.es_retoma is True
    assert res.obra["id"] == obra_planta["id"]
    assert "Planta Cagua" in res.obra["nombre"]

def test_session_manager_nueva_obra():
    chat_id = "55599999"
    session_manager.clear_chat_sessions(chat_id)

    res = session_manager.resolve_context(
        chat_id=chat_id,
        text="Nueva obra: Centro Médico Caracas, remodelar recepción"
    )

    assert res.accion == "nueva_obra"
    assert res.es_nueva_obra is True
    assert "Centro Médico" in res.obra["nombre"]

def test_session_manager_historial_sliding_window():
    chat_id = "55577777"
    session_manager.clear_chat_sessions(chat_id)

    sesion = session_manager.create_session(telegram_chat_id=chat_id, obra_nombre="Obra Test")
    
    # Agregar 12 mensajes alternados (más de 10)
    for i in range(12):
        session_manager.save_session_state(
            chat_id=chat_id,
            session_id=sesion["id"],
            obra_id=None,
            obra_nombre="Obra Test",
            estado="activo",
            rondas_preguntas=1,
            borrador_json={},
            user_msg=f"Mensaje usuario {i}",
            bot_msg=f"Respuesta bot {i}"
        )

    sesion_final = supabase_service.get_sesion_activa_o_esperando(chat_id)
    assert sesion_final is not None
    # No debe exceder MAX_HISTORIAL_TURNOS (10)
    assert len(sesion_final["historial_mensajes"]) <= 10
