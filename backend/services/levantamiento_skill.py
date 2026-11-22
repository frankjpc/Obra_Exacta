import re
import json
import time
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

from services.gemini_service import gemini_service
from services.calculator import PartidaInput

# ==============================================================================
# MODELOS PYDANTIC DEL LOOP DE LEVANTAMIENTO INCISIVO
# ==============================================================================

class PartidaLevantamiento(BaseModel):
    tipo_partida: str = Field(
        default="pared_bloque",
        description="pared_bloque, pintura, ceramica, cielo_raso, lampara, u otro"
    )
    descripcion: str = Field(description="Descripción concisa de la partida")
    codigo_covenin: Optional[str] = None
    largo: float = 0.0
    alto: float = 0.0
    cantidad: float = 1.0
    area: float = 0.0
    unidad: str = "m2"
    espesor: Optional[str] = None  # ej. 15cm, 10cm
    friso: Optional[str] = None    # ej. 1 cara, 2 caras, sin friso
    detalles_material: Optional[str] = None

class DatosAcumulados(BaseModel):
    obra_nombre: Optional[str] = "Obra"
    partidas: List[PartidaLevantamiento] = Field(default_factory=list)
    interferencias: Optional[str] = None
    tipo_superficie: Optional[str] = None
    observaciones_campo: Optional[str] = None
    foto_area_url: Optional[str] = None

class LevantamientoResponse(BaseModel):
    datos_acumulados: DatosAcumulados
    estado: Literal["necesita_aclaracion", "listo_para_presupuestar"]
    pregunta_corta: Optional[str] = Field(
        default=None,
        description="Máximo 2 preguntas técnicas muy breves y directas (<20 palabras) sobre lo que realmente falta"
    )
    solicitar_foto: bool = Field(
        default=True,
        description="True si aún no se tiene la foto del área de trabajo donde se va a trabajar"
    )
    motivo_parada: Optional[str] = None

class LevantamientoSession(BaseModel):
    chat_id: int
    obra_id: str
    round_count: int = 0
    datos_acumulados: DatosAcumulados = Field(default_factory=DatosAcumulados)
    ultimo_mensaje_usuario: Optional[str] = None
    foto_area_url: Optional[str] = None
    updated_at: float = Field(default_factory=time.time)


# ==============================================================================
# SERVICIO DEL LOOP DE LEVANTAMIENTO
# ==============================================================================

class LevantamientoSkillService:
    """
    Asistente técnico de levantamiento incisivo:
    - Acumula medidas y partidas progresivamente.
    - Realiza preguntas cortas directas de campo (< 20 palabras).
    - Aplica condiciones de parada obligatorias (máx 2 rondas o petición explícita).
    - Solicita foto ÚNICAMENTE si hay daño oculto o superficie incierta.
    """

    FRASES_PARADA_EXPLICITA = [
        "calcula asi", "calcula así", "calcula con eso", "calcula ya",
        "genera el presupuesto ya", "genera presupuesto", "saca el presupuesto",
        "con eso basta", "asi esta bien", "así está bien", "listo", "deja eso asi",
        "deja eso así", "saca la cuenta ya", "saca la cuenta", "cotiza ya",
        "con esos datos", "con eso es suficiente"
    ]

    def __init__(self):
        self._sessions: Dict[int, LevantamientoSession] = {}

    def get_session(self, chat_id: int) -> Optional[LevantamientoSession]:
        session = self._sessions.get(chat_id)
        if not session:
            # Intentar recuperar de Supabase si la sesión está esperando aclaración
            from services.supabase_service import supabase_service
            db_s = supabase_service.get_sesion_activa_o_esperando(str(chat_id))
            if db_s:
                session = self.sync_session_from_db(chat_id, db_s)
        return session

    def has_active_session(self, chat_id: int) -> bool:
        if chat_id in self._sessions:
            return True
        # Recuperación persistente desde Supabase
        from services.supabase_service import supabase_service
        db_s = supabase_service.get_sesion_activa_o_esperando(str(chat_id))
        if db_s and db_s.get("estado") in ["activo", "esperando_aclaracion"]:
            self.sync_session_from_db(chat_id, db_s)
            return True
        return False

    def sync_session_from_db(self, chat_id: int, session_db: Dict[str, Any]) -> LevantamientoSession:
        """Restaura o sincroniza una sesión desde Supabase en la memoria activa del asistente."""
        borrador = session_db.get("borrador_json") or {}
        datos = None
        if borrador and isinstance(borrador, dict) and borrador.get("partidas"):
            try:
                datos = DatosAcumulados.model_validate(borrador)
            except Exception as e:
                print(f"Aviso validando borrador_json al sincronizar: {e}")

        if not datos:
            datos = DatosAcumulados(obra_nombre=session_db.get("obra_nombre", "Obra"))

        foto_url = datos.foto_area_url or session_db.get("foto_area_url")
        if foto_url:
            datos.foto_area_url = foto_url

        session = LevantamientoSession(
            chat_id=chat_id,
            obra_id=str(session_db.get("obra_id") or ""),
            round_count=int(session_db.get("rondas_preguntas", 0)),
            datos_acumulados=datos,
            foto_area_url=foto_url
        )
        self._sessions[chat_id] = session
        return session

    def clear_session(self, chat_id: int) -> None:
        if chat_id in self._sessions:
            del self._sessions[chat_id]

    def es_parada_explicita(self, texto: Optional[str]) -> bool:
        if not texto:
            return False
        clean = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]', '', texto.lower()).strip()
        return any(frase in clean for frase in self.FRASES_PARADA_EXPLICITA)

    def evaluar_o_acumular(
        self,
        chat_id: int,
        obra_id: str,
        obra_nombre: str,
        texto_usuario: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        image_bytes: Optional[bytes] = None,
        foto_url: Optional[str] = None,
        historial_mensajes: Optional[List[Dict[str, Any]]] = None,
        mime_type: str = "audio/ogg"
    ) -> LevantamientoResponse:
        """
        Punto de entrada principal del Loop Incisivo.
        Evalúa el estado actual, consulta Gemini o aplica heurística estricta,
        y devuelve LevantamientoResponse.
        """
        session = self._sessions.get(chat_id)
        if not session:
            session = LevantamientoSession(
                chat_id=chat_id,
                obra_id=obra_id,
                round_count=0,
                datos_acumulados=DatosAcumulados(obra_nombre=obra_nombre)
            )
            self._sessions[chat_id] = session

        session.obra_id = obra_id
        session.updated_at = time.time()
        texto_str = texto_usuario or ""

        if foto_url:
            session.foto_area_url = foto_url
            session.datos_acumulados.foto_area_url = foto_url

        # ----------------------------------------------------------------------
        # CONDICIÓN DE PARADA 1: El usuario dijo explícitamente "calcula así" / "con eso basta"
        # ----------------------------------------------------------------------
        if self.es_parada_explicita(texto_str):
            if session.datos_acumulados.partidas:
                return LevantamientoResponse(
                    datos_acumulados=session.datos_acumulados,
                    estado="listo_para_presupuestar",
                    pregunta_corta=None,
                    solicitar_foto=False,
                    motivo_parada="Usuario solicitó calcular con los datos existentes."
                )

        # ----------------------------------------------------------------------
        # CONDICIÓN DE PARADA 2: Máximo 2 rondas de preguntas ya cumplidas
        # ----------------------------------------------------------------------
        if session.round_count >= 2:
            self._normalizar_partidas_incompletas(session.datos_acumulados)
            return LevantamientoResponse(
                datos_acumulados=session.datos_acumulados,
                estado="listo_para_presupuestar",
                pregunta_corta=None,
                solicitar_foto=False,
                motivo_parada="Límite de 2 rondas de preguntas alcanzado. Aplicando estándares COVENIN."
            )

        # ----------------------------------------------------------------------
        # CONSULTA ESTRUCTURADA A GEMINI
        # ----------------------------------------------------------------------
        gemini_result = self._consultar_gemini_loop(
            session=session,
            texto_usuario=texto_str,
            audio_bytes=audio_bytes,
            image_bytes=image_bytes,
            historial_mensajes=historial_mensajes,
            mime_type=mime_type,
            obra_nombre=obra_nombre
        )

        if gemini_result:
            if session.foto_area_url:
                gemini_result.datos_acumulados.foto_area_url = session.foto_area_url
                gemini_result.solicitar_foto = False

            # Actualizar datos acumulados en la sesión
            session.datos_acumulados = gemini_result.datos_acumulados

            # Si el usuario solicitó explícitamente parada durante la respuesta
            if self.es_parada_explicita(texto_str) or session.round_count >= 2:
                gemini_result.estado = "listo_para_presupuestar"
                gemini_result.pregunta_corta = None
                gemini_result.solicitar_foto = False

            # Si necesita aclaración, incrementar el contador de rondas
            if gemini_result.estado == "necesita_aclaracion":
                session.round_count += 1
                if not session.foto_area_url:
                    gemini_result.solicitar_foto = True
            else:
                # Si está listo para presupuestar pero falta foto del área en la primera ronda
                if not session.foto_area_url and session.round_count == 0 and not image_bytes and not self.es_parada_explicita(texto_str):
                    gemini_result.estado = "necesita_aclaracion"
                    gemini_result.pregunta_corta = "¿Podrías enviar una foto del área donde se va a trabajar? (o dime 'calcula así' para presupuestar ya)"
                    gemini_result.solicitar_foto = True
                    session.round_count += 1
                else:
                    self._normalizar_partidas_incompletas(session.datos_acumulados)

            return gemini_result

        # ----------------------------------------------------------------------
        # FALLBACK HEURÍSTICO SI GEMINI NO RESPONDE
        # ----------------------------------------------------------------------
        return self._fallback_heuristico_loop(session, texto_str, obra_nombre)

    def _consultar_gemini_loop(
        self,
        session: LevantamientoSession,
        texto_usuario: str,
        audio_bytes: Optional[bytes],
        image_bytes: Optional[bytes],
        historial_mensajes: Optional[List[Dict[str, Any]]] = None,
        mime_type: str = "audio/ogg",
        obra_nombre: str = "Obra"
    ) -> Optional[LevantamientoResponse]:
        """Envía el contexto acumulado y el nuevo mensaje a Gemini con el esquema Pydantic."""
        datos_actuales_json = json.dumps(session.datos_acumulados.model_dump(), ensure_ascii=False)

        historial_str = ""
        if historial_mensajes:
            for m in historial_mensajes[-8:]:
                historial_str += f"- {m.get('role', 'user')}: {m.get('content', '')}\n"

        system_instruction = (
            "Eres el Asistente Técnico de Levantamiento de Obras de ObraExacta en Venezuela. "
            "Tu tarea es recopilar datos técnicos de construcción para cotizar según Norma COVENIN. "
            "Operas en un 'Loop de Levantamiento Incisivo'.\n\n"
            f"DATOS ACUMULADOS HASTA AHORA (NO LOS BORRES, FUSIÓNALOS CON LO NUEVO):\n{datos_actuales_json}\n"
            + (f"\nHISTORIAL RECIENTE DE LA CONVERSACIÓN:\n{historial_str}\n" if historial_str else "")
            + f"RONDA DE PREGUNTAS ACTUAL: {session.round_count} (Máximo 2).\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. CONDICIÓN DE PARADA ('listo_para_presupuestar'):\n"
            "   - Pon estado='listo_para_presupuestar' si ya tienes dimensiones (largo x alto o m2) y material esencial de las partidas.\n"
            f"   - Si la ronda actual es >= 2, SIEMPRE pon estado='listo_para_presupuestar' y pregunta_corta=null.\n"
            "   - Si el usuario dice 'calcula así', 'con eso basta', 'genera el presupuesto' o similar, SIEMPRE pon estado='listo_para_presupuestar'.\n\n"
            "2. ESTADO 'necesita_aclaracion':\n"
            "   - Pon estado='necesita_aclaracion' si falta un dato crítico de costo (ej. no sabemos si es bloque o drywall, falta el espesor 10 vs 15cm, o falta la altura/área).\n\n"
            "3. PREGUNTA CORTA (pregunta_corta):\n"
            "   - Máximo 2 preguntas técnicas directas, estilo mensaje de campo, MENOS DE 20 PALABRAS TOTALES.\n"
            "   - Ejemplos válidos:\n"
            "     * '¿Es bloque de 15 o de 10cm? ¿Lleva friso en ambas caras?'\n"
            "     * '¿Pared de bloque o drywall? ¿Qué altura tiene?'\n"
            "     * '¿Pintura interior o exterior? ¿Cuántas manos?'\n"
            "   - NO uses saludos ni explicaciones largas. Ve directo al grano técnico.\n\n"
            "4. REGLA DE FOTO DEL ÁREA DE TRABAJO (solicitar_foto):\n"
            "   - El usuario solicita siempre pedir una foto del área donde se va a trabajar para inspección visual.\n"
            "   - Si la sesión aún no tiene foto del área (foto_area_url es null), pon solicitar_foto=true.\n"
            "   - Si ya se recibió foto del área (o en este turno viene foto), pon solicitar_foto=false.\n"
            "   - Si el usuario dice 'calcula así' o 'con eso basta', pon solicitar_foto=false.\n\n"
            "Devuelve ÚNICAMENTE un JSON con esta estructura exacta:\n"
            "{\n"
            '  "datos_acumulados": {\n'
            f'    "obra_nombre": "{obra_nombre}",\n'
            '    "partidas": [\n'
            '      {\n'
            '        "tipo_partida": "pared_bloque" | "pintura" | "ceramica" | "cielo_raso" | "lampara" | "otro",\n'
            '        "descripcion": "Descripción concisa con dimensiones",\n'
            '        "largo": 0.0,\n'
            '        "alto": 0.0,\n'
            '        "cantidad": 1.0,\n'
            '        "area": 0.0,\n'
            '        "unidad": "m2" | "piezas" | "und",\n'
            '        "espesor": "15cm" | "10cm" | null,\n'
            '        "friso": "dos caras" | "una cara" | "sin friso" | null,\n'
            '        "detalles_material": "..."\n'
            '      }\n'
            '    ],\n'
            '    "interferencias": "tuberías, cableado, o null",\n'
            '    "tipo_superficie": "...",\n'
            '    "observaciones_campo": "...",\n'
            '    "foto_area_url": null\n'
            '  },\n'
            '  "estado": "necesita_aclaracion" | "listo_para_presupuestar",\n'
            '  "pregunta_corta": "Pregunta técnica directa (<20 palabras) o null",\n'
            '  "solicitar_foto": true,\n'
            '  "motivo_parada": "..."\n'
            "}"
        )

        parts = []
        if image_bytes:
            import base64
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode("utf-8")
                }
            })
            parts.append({"text": "Esta es la foto del área donde se va a trabajar. Analízala para identificar tipo de superficie, material e interferencias."})
        if audio_bytes:
            import base64
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(audio_bytes).decode("utf-8")
                }
            })
            prompt_texto = texto_usuario or "Analiza las medidas técnicas de este audio e intégralas a los datos acumulados."
            parts.append({"text": prompt_texto})
        elif texto_usuario:
            parts.append({"text": texto_usuario})
        elif not image_bytes:
            return None

        res_text = gemini_service._call_gemini_rest(parts, system_instruction)
        if res_text:
            try:
                cleaned = re.sub(r"^```json\s*", "", res_text.strip())
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                return LevantamientoResponse.model_validate(data)
            except Exception as e:
                print(f"Error decodificando LevantamientoResponse de Gemini: {e}")
        return None

    def _fallback_heuristico_loop(
        self,
        session: LevantamientoSession,
        texto: str,
        obra_nombre: str
    ) -> LevantamientoResponse:
        """Fallback si Gemini no está disponible."""
        lower = texto.lower()
        solicitar_foto = (session.foto_area_url is None) and (not self.es_parada_explicita(texto)) and (session.round_count < 2)

        # Detección de parada
        if self.es_parada_explicita(texto) or session.round_count >= 2:
            self._normalizar_partidas_incompletas(session.datos_acumulados)
            return LevantamientoResponse(
                datos_acumulados=session.datos_acumulados,
                estado="listo_para_presupuestar",
                pregunta_corta=None,
                solicitar_foto=False,
                motivo_parada="Finalizado por regla de parada heurística."
            )

        # Detectar medidas básicas
        dims = re.findall(r"(\d+(?:\.\d+)?)\s*(?:m|metros)?\s*(?:x|por|de largo)\s*(\d+(?:\.\d+)?)", lower)
        largo, alto = 0.0, 0.0
        if dims:
            try:
                largo = float(dims[0][0])
                alto = float(dims[0][1])
            except Exception:
                pass

        if "pared" in lower or "bloque" in lower:
            espesor = "15cm" if "15" in lower else ("10cm" if "10" in lower else None)
            friso = "dos caras" if ("dos cara" in lower or "ambas" in lower) else ("una cara" if "una cara" in lower else None)
            
            p = PartidaLevantamiento(
                tipo_partida="pared_bloque",
                descripcion=f"Pared de bloques ({largo}m x {alto}m)" if largo and alto else "Pared de bloques de arcilla",
                largo=largo,
                alto=alto,
                area=round(largo * alto, 2) if (largo and alto) else 0.0,
                espesor=espesor,
                friso=friso
            )
            session.datos_acumulados.partidas.append(p)

            if not espesor and session.round_count < 2:
                session.round_count += 1
                return LevantamientoResponse(
                    datos_acumulados=session.datos_acumulados,
                    estado="necesita_aclaracion",
                    pregunta_corta="¿Es bloque de 15 o de 10cm? ¿Lleva friso en ambas caras?",
                    solicitar_foto=solicitar_foto
                )

        if session.datos_acumulados.partidas:
            if not session.foto_area_url and session.round_count == 0 and not self.es_parada_explicita(texto):
                session.round_count += 1
                return LevantamientoResponse(
                    datos_acumulados=session.datos_acumulados,
                    estado="necesita_aclaracion",
                    pregunta_corta="¿Podrías enviar una foto del área donde se va a trabajar?",
                    solicitar_foto=True
                )
            self._normalizar_partidas_incompletas(session.datos_acumulados)
            return LevantamientoResponse(
                datos_acumulados=session.datos_acumulados,
                estado="listo_para_presupuestar",
                pregunta_corta=None,
                solicitar_foto=False
            )

        session.round_count += 1
        return LevantamientoResponse(
            datos_acumulados=session.datos_acumulados,
            estado="necesita_aclaracion",
            pregunta_corta="¿Qué dimensiones aproximadas tiene la pared o superficie?",
            solicitar_foto=solicitar_foto
        )

    def _normalizar_partidas_incompletas(self, datos: DatosAcumulados):
        """Asume estándares COVENIN constructivos para cualquier partida que falte detallar."""
        for p in datos.partidas:
            if p.tipo_partida == "pared_bloque":
                if not p.espesor:
                    p.espesor = "15cm"
                if not p.friso:
                    p.friso = "dos caras"
                if p.largo <= 0 and p.alto <= 0 and p.area <= 0:
                    p.largo, p.alto = 6.0, 2.60
                    p.area = 15.60
                elif p.largo > 0 and p.alto > 0 and p.area <= 0:
                    p.area = round(p.largo * p.alto, 2)
            elif p.tipo_partida == "pintura":
                if p.area <= 0:
                    p.area = 50.0

    def convertir_a_partidas_calculator(self, datos: DatosAcumulados) -> List[PartidaInput]:
        """Convierte las partidas acumuladas en PartidaInput para ConstructionCalculator."""
        self._normalizar_partidas_incompletas(datos)
        resultado = []
        for p in datos.partidas:
            desc = p.descripcion
            detalles = []
            if p.espesor:
                detalles.append(f"e={p.espesor}")
            if p.friso:
                detalles.append(f"friso {p.friso}")
            if detalles and not any(d in desc.lower() for d in detalles):
                desc = f"{desc} ({', '.join(detalles)})"

            resultado.append(
                PartidaInput(
                    tipo_partida=p.tipo_partida,
                    descripcion=desc,
                    codigo_covenin=p.codigo_covenin,
                    largo=p.largo,
                    alto=p.alto,
                    cantidad=p.cantidad if p.cantidad > 0 else 1.0,
                    area=p.area,
                    unidad=p.unidad or "m2"
                )
            )
        return resultado

levantamiento_skill = LevantamientoSkillService()
