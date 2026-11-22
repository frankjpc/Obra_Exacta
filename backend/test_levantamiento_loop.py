from services.levantamiento_skill import (
    levantamiento_skill,
    DatosAcumulados,
    PartidaLevantamiento
)

def test_parada_explicita():
    assert levantamiento_skill.es_parada_explicita("calcula así por favor")
    assert levantamiento_skill.es_parada_explicita("con eso basta")
    assert levantamiento_skill.es_parada_explicita("genera el presupuesto ya")
    assert not levantamiento_skill.es_parada_explicita("pared de bloque 6x2.60")

def test_loop_maximo_2_rondas():
    chat_id = 999999
    levantamiento_skill.clear_session(chat_id)

    # Ronda 1
    res1 = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        texto_usuario="Tengo que levantar una pared de 6 por 2.80"
    )
    # Puede ser necesita_aclaracion o listo si reconoció todo
    if res1.estado == "necesita_aclaracion":
        assert len(res1.pregunta_corta.split()) < 25
        assert res1.solicitar_foto is True

    # Simular que llegamos a 2 rondas
    session = levantamiento_skill.get_session(chat_id)
    session.round_count = 2

    # Siguiente interacción DEBE forzar parada
    res_final = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        texto_usuario="algo mas"
    )
    assert res_final.estado == "listo_para_presupuestar"
    assert res_final.pregunta_corta is None

def test_parada_usuario_calcula_asi():
    chat_id = 888888
    levantamiento_skill.clear_session(chat_id)
    
    # Preparar datos
    _ = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        texto_usuario="Pared de 5x2.50"
    )
    
    # Usuario dice "calcula así"
    res2 = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        texto_usuario="calcula así"
    )
    assert res2.estado == "listo_para_presupuestar"
    assert res2.pregunta_corta is None

def test_conversion_a_partidas_calculator():
    datos = DatosAcumulados(
        obra_nombre="Obra Test",
        partidas=[
            PartidaLevantamiento(
                tipo_partida="pared_bloque",
                descripcion="Pared de bloque",
                largo=6.0,
                alto=2.80,
                espesor="15cm",
                friso="dos caras"
            )
        ]
    )
    partidas_calc = levantamiento_skill.convertir_a_partidas_calculator(datos)
    assert len(partidas_calc) == 1
    p = partidas_calc[0]
    assert p.tipo_partida == "pared_bloque"
    assert p.largo == 6.0
    assert p.alto == 2.80
    assert p.area == round(6.0 * 2.80, 2)
    assert "e=15cm" in p.descripcion

def test_solicitar_y_recibir_foto_area():
    chat_id = 777777
    levantamiento_skill.clear_session(chat_id)

    # 1. El usuario envía medidas por primera vez
    res1 = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        texto_usuario="Pared de 6x2.80"
    )
    # Debe solicitar foto del área de trabajo
    assert res1.solicitar_foto is True
    session = levantamiento_skill.get_session(chat_id)
    assert session.foto_area_url is None

    # 2. El usuario envía la foto del área solicitada
    res2 = levantamiento_skill.evaluar_o_acumular(
        chat_id=chat_id,
        obra_id="test-obra",
        obra_nombre="Test Obra",
        foto_url="https://ejemplo.com/uploads/foto_area.jpg",
        texto_usuario="es bloque de 15cm con friso dos caras"
    )
    # Al recibir la foto, queda guardada en la sesión y no se vuelve a pedir
    assert res2.datos_acumulados.foto_area_url == "https://ejemplo.com/uploads/foto_area.jpg"
    assert res2.solicitar_foto is False
    assert res2.estado == "listo_para_presupuestar"
