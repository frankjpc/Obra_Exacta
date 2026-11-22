import re
import json
import uuid
import datetime
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field

from services.supabase_service import supabase_service
from services.gemini_service import gemini_service

# ==============================================================================
# MODELOS PYDANTIC DEL GESTOR DE SESIONES Y CONTEXTO
# ==============================================================================

class MensajeHistorial(BaseModel):
    role: str = Field(description="'user' o 'assistant'")
    content: str = Field(description="Texto del mensaje")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

class SesionLevantamientoDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_chat_id: str
    user_id: Optional[str] = None
    obra_id: Optional[str] = None
    obra_nombre: Optional[str] = "Obra"
    estado: str = Field(default="activo")  # 'activo', 'esperando_aclaracion', 'completado'
    rondas_preguntas: int = 0
    borrador_json: Dict[str, Any] = Field(default_factory=dict)
    historial_mensajes: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    created_at: Optional[str] = None

class ContextResolution(BaseModel):
    accion: str  # 'respuesta_aclaracion', 'retoma_obra', 'nueva_obra', 'obra_actual'
    obra: Dict[str, Any]
    session_db: Dict[str, Any]
    es_retoma: bool = False
    es_nueva_obra: bool = False
    mensaje_aviso: Optional[str] = None


# ==============================================================================
# ORQUESTADOR Y ROUTER DE SESIONES
# ==============================================================================

class SessionManager:
    """
    Capa de orquestación y enrutamiento inteligente de contexto para ObraExacta:
    1. Recupera o crea sesiones persistidas en Supabase (tabla 'sesiones_levantamiento').
    2. Detecta si el usuario está en medio de una aclaración ('esperando_aclaracion').
    3. Consulta obras recientes del chat y clasifica con Gemini si retoma una obra previa o inicia una nueva.
    4. Mantiene un historial deslizante de los últimos 10 turnos de conversación.
    5. Carga y guarda automáticamente el 'borrador_json' de cómputos métricos.
    """

    MAX_HISTORIAL_TURNOS = 10

    def resolve_context(
        self,
        chat_id: Union[str, int],
        text: Optional[str] = None,
        audio_transcript: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ContextResolution:
        """
        Punto de entrada orquestador. Determina el contexto exacto de obra y sesión.
        """
        str_chat_id = str(chat_id)
        texto_eval = (text or audio_transcript or "").strip()

        # Resolver user_id automáticamente desde perfiles_telegram si no se especificó
        if not user_id:
            perfil = supabase_service.get_perfil_by_chat_id(str_chat_id)
            if perfil:
                user_id = perfil.get("user_id")

        # ----------------------------------------------------------------------
        # REGLA 1: Si ya tiene una sesión en estado 'esperando_aclaracion',
        # asume que el mensaje es la respuesta directa a la pregunta previa del loop.
        # ----------------------------------------------------------------------
        sesion_activa = supabase_service.get_sesion_activa_o_esperando(str_chat_id)
        if sesion_activa and sesion_activa.get("estado") == "esperando_aclaracion":
            obra_id = sesion_activa.get("obra_id")
            obra = supabase_service.get_obra(obra_id) if obra_id else None
            if not obra:
                int_cid = int(str_chat_id) if str_chat_id.isdigit() else None
                obra = supabase_service.get_or_create_active_obra(int_cid, user_id=user_id)
                sesion_activa["obra_id"] = obra["id"]
                sesion_activa["obra_nombre"] = obra.get("nombre", "Obra")
            if user_id and not sesion_activa.get("user_id"):
                sesion_activa["user_id"] = user_id
            supabase_service.save_sesion(sesion_activa)

            return ContextResolution(
                accion="respuesta_aclaracion",
                obra=obra,
                session_db=sesion_activa,
                es_retoma=False,
                es_nueva_obra=False
            )

        # ----------------------------------------------------------------------
        # REGLA 2: Consultar obras recientes para este telegram_chat_id / user_id
        # ----------------------------------------------------------------------
        obras_recientes = supabase_service.get_recent_obras(str_chat_id, user_id=user_id, limit=6)

        # Si hay texto y obras previas, consultar a Gemini para detectar si retoma una obra o inicia una nueva
        if texto_eval and obras_recientes:
            deteccion = self._detectar_intencion_obra_gemini(texto_eval, obras_recientes)
            
            # Caso A: El usuario indica explícitamente que es una nueva obra
            if deteccion.get("es_nueva_obra") and deteccion.get("nombre_obra"):
                int_cid = int(str_chat_id) if str_chat_id.isdigit() else None
                nombre_nuevo = deteccion.get("nombre_obra") or "Nueva Obra"
                nueva_obra = supabase_service.create_obra({
                    "nombre": nombre_nuevo,
                    "cliente": "Cliente General",
                    "estado": "activa",
                    "telegram_chat_id": int_cid,
                    "user_id": user_id
                }, user_id=user_id)
                # Crear sesión limpia enlazada a la nueva obra
                session_db = self.create_session(
                    telegram_chat_id=str_chat_id,
                    obra_id=nueva_obra["id"],
                    obra_nombre=nueva_obra["nombre"],
                    estado="activo",
                    user_id=user_id
                )
                return ContextResolution(
                    accion="nueva_obra",
                    obra=nueva_obra,
                    session_db=session_db,
                    es_retoma=False,
                    es_nueva_obra=True,
                    mensaje_aviso=f"🆕 *Iniciando nueva obra:* `{nueva_obra['nombre']}`"
                )

            # Caso B: El usuario retoma una obra anterior existente
            elif deteccion.get("retoma_obra") and deteccion.get("obra_id"):
                target_id = deteccion["obra_id"]
                target_obra = supabase_service.get_obra(target_id)
                if target_obra:
                    # Activar esta obra para el chat
                    supabase_service.set_active_obra(str_chat_id, target_obra["id"])
                    
                    # Cargar la sesión previa de esta obra o crear una enlazada
                    session_db = supabase_service.get_sesion_by_obra(str_chat_id, target_obra["id"])
                    if not session_db:
                        session_db = self.create_session(
                            telegram_chat_id=str_chat_id,
                            obra_id=target_obra["id"],
                            obra_nombre=target_obra["nombre"],
                            estado="activo",
                            user_id=user_id
                        )
                    else:
                        # Si estaba completada, reactivarla para continuar trabajando sobre ella
                        session_db["estado"] = "activo"
                        if user_id and not session_db.get("user_id"):
                            session_db["user_id"] = user_id
                        supabase_service.save_sesion(session_db)

                    return ContextResolution(
                        accion="retoma_obra",
                        obra=target_obra,
                        session_db=session_db,
                        es_retoma=True,
                        es_nueva_obra=False,
                        mensaje_aviso=f"🔄 *Retomando contexto de obra:* `{target_obra['nombre']}`"
                    )

        # ----------------------------------------------------------------------
        # REGLA 3: Continuar sobre la obra activa actual del chat / usuario
        # ----------------------------------------------------------------------
        int_cid = int(str_chat_id) if str_chat_id.isdigit() else None
        obra_activa = supabase_service.get_or_create_active_obra(int_cid, user_id=user_id)
        
        session_db = sesion_activa
        if not session_db:
            # Buscar sesión previa para esta obra activa
            session_db = supabase_service.get_sesion_by_obra(str_chat_id, obra_activa["id"])
        
        if not session_db:
            session_db = self.create_session(
                telegram_chat_id=str_chat_id,
                obra_id=obra_activa["id"],
                obra_nombre=obra_activa.get("nombre", "Obra"),
                estado="activo",
                user_id=user_id
            )
        else:
            session_db["obra_id"] = obra_activa["id"]
            session_db["obra_nombre"] = obra_activa.get("nombre", "Obra")
            if user_id and not session_db.get("user_id"):
                session_db["user_id"] = user_id
            if session_db.get("estado") == "completado":
                session_db["estado"] = "activo"
            supabase_service.save_sesion(session_db)

        return ContextResolution(
            accion="obra_actual",
            obra=obra_activa,
            session_db=session_db,
            es_retoma=False,
            es_nueva_obra=False
        )

    def create_session(
        self,
        telegram_chat_id: str,
        obra_id: Optional[str] = None,
        obra_nombre: Optional[str] = "Obra",
        estado: str = "activo",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Crea y persiste una nueva sesión de levantamiento."""
        sesion_obj = SesionLevantamientoDB(
            telegram_chat_id=str(telegram_chat_id),
            user_id=user_id,
            obra_id=obra_id,
            obra_nombre=obra_nombre or "Obra",
            estado=estado,
            rondas_preguntas=0,
            borrador_json={},
            historial_mensajes=[]
        )
        return supabase_service.save_sesion(sesion_obj.model_dump())

    def save_session_state(
        self,
        chat_id: Union[str, int],
        session_id: str,
        obra_id: Optional[str],
        obra_nombre: str,
        estado: str,
        rondas_preguntas: int,
        borrador_json: Dict[str, Any],
        user_msg: Optional[str] = None,
        bot_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza el borrador_json, estado, contador de rondas y mantiene la ventana deslizante
        de los últimos 10 turnos de mensajes en historial_mensajes.
        """
        str_chat_id = str(chat_id)
        sesion = supabase_service.get_sesion_activa_o_esperando(str_chat_id)
        if not sesion or sesion.get("id") != session_id:
            sesion = supabase_service.get_sesion_by_obra(str_chat_id, obra_id) if obra_id else None
        
        historial: List[Dict[str, Any]] = sesion.get("historial_mensajes", []) if sesion else []

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if user_msg:
            historial.append({
                "role": "user",
                "content": str(user_msg),
                "timestamp": now_iso
            })
        if bot_msg:
            historial.append({
                "role": "assistant",
                "content": str(bot_msg),
                "timestamp": now_iso
            })

        # Limitar estrictamente a los últimos 10 turnos
        if len(historial) > self.MAX_HISTORIAL_TURNOS:
            historial = historial[-self.MAX_HISTORIAL_TURNOS:]

        item = {
            "id": session_id,
            "telegram_chat_id": str_chat_id,
            "obra_id": obra_id,
            "obra_nombre": obra_nombre,
            "estado": estado,
            "rondas_preguntas": rondas_preguntas,
            "borrador_json": borrador_json,
            "historial_mensajes": historial
        }
        return supabase_service.save_sesion(item)

    def complete_session(
        self,
        chat_id: Union[str, int],
        session_id: str,
        borrador_final: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Marca la sesión como completada en Supabase y guarda el borrador final."""
        return supabase_service.complete_sesion(session_id, borrador_final)

    def clear_chat_sessions(self, chat_id: Union[str, int]) -> None:
        """Limpia las sesiones de este chat."""
        supabase_service.clear_sesiones_chat(str(chat_id))

    def _detectar_intencion_obra_gemini(
        self,
        texto_usuario: str,
        obras_recientes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Usa Gemini para clasificar si el usuario retoma una obra anterior o inicia una nueva.
        """
        if not texto_usuario or not obras_recientes:
            return {"retoma_obra": False, "es_nueva_obra": False, "obra_id": None}

        lower = texto_usuario.lower().strip()
        # Detección determinista inmediata si empieza con prefijo explícito de nueva obra
        if any(lower.startswith(prefix) for prefix in ["nueva obra", "nuevo proyecto", "obra nueva", "proyecto nuevo"]):
            nombre_sug = re.sub(r"^(nueva obra|nuevo proyecto|obra nueva|proyecto nuevo)[:\s-]*", "", texto_usuario, flags=re.I).strip()
            return {
                "retoma_obra": False,
                "es_nueva_obra": True,
                "obra_id": None,
                "nombre_obra": nombre_sug[:50] if nombre_sug else "Nuevo Proyecto",
                "razon": "Prefijo explícito de inicio de nueva obra"
            }

        obras_info = [
            {"id": str(o.get("id")), "nombre": o.get("nombre", ""), "cliente": o.get("cliente", "")}
            for o in obras_recientes
        ]

        system_instruction = (
            "Eres el Orquestador de Sesiones y Contexto de ObraExacta en Venezuela. "
            "Tu tarea es analizar el mensaje del usuario y compararlo con las obras recientes registradas para determinar:\n"
            "1. ¿El usuario se refiere o retoma alguna obra existente de la lista? "
            "(ej. 'sobre la obra de la planta...', 'en la oficina de ayer...', 'agrega 20m2 a la casa de campo...').\n"
            "   -> Pon retoma_obra=true y obra_id='uuid correspondiente'.\n"
            "2. ¿El usuario indica explícitamente iniciar o crear una obra o proyecto nuevo? "
            "(ej. 'nueva obra: Galpón Guacara...', 'vamos a cotizar un nuevo proyecto...', 'para la nueva remodelación...').\n"
            "   -> Pon es_nueva_obra=true y nombre_obra='Nombre conciso sugerido'.\n"
            "3. ¿El usuario solo dicta medidas o responde sin mencionar otra obra? (ej. 'pared 6x2.80', 'bloque de 15', 'calcula así').\n"
            "   -> Pon retoma_obra=false, es_nueva_obra=false, obra_id=null.\n\n"
            f"OBRAS RECIENTES REGISTRADAS:\n{json.dumps(obras_info, ensure_ascii=False)}\n\n"
            "Devuelve ÚNICAMENTE un JSON con esta estructura exacta:\n"
            "{\n"
            '  "retoma_obra": true | false,\n'
            '  "obra_id": "uuid" | null,\n'
            '  "es_nueva_obra": true | false,\n'
            '  "nombre_obra": "Nombre sugerido o null",\n'
            '  "razon": "Explicación breve"\n'
            "}"
        )

        parts = [{"text": texto_usuario}]
        res_text = gemini_service._call_gemini_rest(parts, system_instruction)
        if res_text:
            try:
                cleaned = re.sub(r"^```json\s*", "", res_text.strip())
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                return data
            except Exception as e:
                print(f"Aviso decodificando intención de obra en Gemini: {e}")

        # Fallback heurístico
        return self._fallback_heuristico_obra(texto_usuario, obras_recientes)

    def _fallback_heuristico_obra(
        self,
        texto: str,
        obras_recientes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback heurístico determinista si Gemini no responde."""
        lower = texto.lower()

        # Detección de nueva obra explícita
        if any(lower.startswith(prefix) for prefix in ["nueva obra", "nuevo proyecto", "obra nueva", "proyecto nuevo"]):
            nombre_sug = re.sub(r"^(nueva obra|nuevo proyecto|obra nueva|proyecto nuevo)[:\s-]*", "", texto, flags=re.I).strip()
            return {
                "retoma_obra": False,
                "es_nueva_obra": True,
                "obra_id": None,
                "nombre_obra": nombre_sug[:50] if nombre_sug else "Nuevo Proyecto",
                "razon": "Comando explícito de nueva obra"
            }

        # Detección de coincidencia por palabra clave con nombres de obras existentes
        for o in obras_recientes:
            nombre = str(o.get("nombre", "")).lower()
            palabras = [p for p in re.split(r"\W+", nombre) if len(p) >= 4]
            if any(p in lower for p in palabras):
                return {
                    "retoma_obra": True,
                    "obra_id": str(o.get("id")),
                    "es_nueva_obra": False,
                    "nombre_obra": o.get("nombre"),
                    "razon": f"Coincidencia con '{o.get('nombre')}'"
                }

        return {
            "retoma_obra": False,
            "es_nueva_obra": False,
            "obra_id": None,
            "nombre_obra": None,
            "razon": "Sin referencia explícita a otra obra"
        }

session_manager = SessionManager()
