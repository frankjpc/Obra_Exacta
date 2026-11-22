import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from services.supabase_service import supabase_service
from services.calculator import ConstructionCalculator, PartidaInput
from services.gemini_service import gemini_service
from services.invoice_service import invoice_service
from services.site_log_service import site_log_service
from services.bcv_service import bcv_service
from bot.telegram_bot import telegram_bot

router = APIRouter(prefix="/api", tags=["ObraExacta API"])

# ------------------------------------------------------------------------------
# MODELOS PYDANTIC PARA ENDPOINTS
# ------------------------------------------------------------------------------
class ObraCreate(BaseModel):
    nombre: str
    cliente: str
    direccion: Optional[str] = ""
    tasa_bcv: Optional[float] = 68.50
    margen_meta: Optional[float] = 30.0
    user_id: Optional[str] = None
    telegram_chat_id: Optional[int] = None

class ObraUpdate(BaseModel):
    nombre: Optional[str] = None
    cliente: Optional[str] = None
    direccion: Optional[str] = None
    tasa_bcv: Optional[float] = None
    margen_meta: Optional[float] = None
    presupuesto_total_usd: Optional[float] = None
    presupuesto_total_bs: Optional[float] = None
    total_gastado_usd: Optional[float] = None
    total_gastado_bs: Optional[float] = None
    estado: Optional[str] = None

class LevantamientoTextoInput(BaseModel):
    obra_id: str
    texto: str
    tasa_bcv: Optional[float] = None

class PartidaManualCreate(BaseModel):
    obra_id: str
    tipo_partida: str
    descripcion: str
    largo: Optional[float] = 0.0
    alto: Optional[float] = 0.0
    cantidad: Optional[float] = 1.0
    area: Optional[float] = 0.0
    unidad: Optional[str] = "m2"
    p_unit_usd: Optional[float] = 0.0

class PartidaAvanceUpdate(BaseModel):
    porcentaje: float

class AprobacionInput(BaseModel):
    cliente_nombre: Optional[str] = "Cliente Autorizado"

class MemoriaPrecioInput(BaseModel):
    clave_o_codigo: str
    nombre: Optional[str] = None
    tipo: Optional[str] = "material"
    unidad: Optional[str] = "und"
    precio_usd: float
    proveedor_opcional: Optional[str] = None

# ------------------------------------------------------------------------------
# ESTADO GENERAL Y DEMO
# ------------------------------------------------------------------------------
@router.get("/status")
def get_system_status():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "gemini_active": bool(gemini_service.client),
        "supabase_connected": supabase_service.is_connected,
        "telegram_bot_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "telegram_bot_status": telegram_bot.bot_info,
        "tasa_bcv_default": settings.TASA_BCV_DEFAULT
    }

@router.post("/seed-demo")
def seed_demo():
    """Carga los datos iniciales de una obra completa para pruebas instantáneas."""
    res = supabase_service.seed_demo_data()
    return res

@router.post("/reset-data")
@router.post("/limpiar-datos")
def reset_database():
    """Limpia completamente todas las tablas de la base de datos y crea un proyecto en blanco."""
    res = supabase_service.clear_all_data(create_default=True)
    return res

# ------------------------------------------------------------------------------
# OBRAS
# ------------------------------------------------------------------------------
@router.get("/obras")
def list_obras(user_id: Optional[str] = None):
    return supabase_service.get_obras(user_id=user_id)

@router.get("/obras/{obra_id}")
def get_obra(obra_id: str):
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    return obra

@router.post("/obras")
def create_obra(data: ObraCreate):
    return supabase_service.create_obra(data.model_dump(), user_id=data.user_id)

@router.patch("/obras/{obra_id}")
def update_obra(obra_id: str, data: ObraUpdate):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    updated = supabase_service.update_obra(obra_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    return updated

# ------------------------------------------------------------------------------
# PARTIDAS Y PRESUPUESTOS (RESPALDO WEB TOTAL)
# ------------------------------------------------------------------------------
@router.get("/obras/{obra_id}/partidas")
def list_partidas(obra_id: str):
    return supabase_service.get_partidas(obra_id)

@router.post("/obras/{obra_id}/partidas")
def add_partida_manual(obra_id: str, data: PartidaManualCreate):
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))

    partida_input = PartidaInput(
        tipo_partida=data.tipo_partida,
        descripcion=data.descripcion,
        largo=data.largo,
        alto=data.alto,
        cantidad=data.cantidad,
        area=data.area,
        unidad=data.unidad,
        p_unit_usd_override=data.p_unit_usd if data.p_unit_usd and data.p_unit_usd > 0 else None
    )
    calculada = ConstructionCalculator.calcular_partida(partida_input, tasa_bcv)
    p_dict = calculada.model_dump()
    p_dict["obra_id"] = obra_id
    saved = supabase_service.save_partida(p_dict)
    return saved

@router.patch("/partidas/{partida_id}/avance")
def update_avance_partida(partida_id: str, data: PartidaAvanceUpdate):
    updated = supabase_service.update_partida_avance(partida_id, data.porcentaje)
    if not updated:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    return updated

# ------------------------------------------------------------------------------
# HOJA DE COMPRAS ESTIMADA
# ------------------------------------------------------------------------------
@router.get("/obras/{obra_id}/hoja-compras")
def get_hoja_compras(obra_id: str):
    return supabase_service.get_hoja_compras(obra_id)

# ------------------------------------------------------------------------------
# LEVANTAMIENTO POR VOZ / TEXTO (RESPALDO WEB TOTAL)
# ------------------------------------------------------------------------------
@router.post("/levantamiento/texto")
def procesar_levantamiento_texto(data: LevantamientoTextoInput):
    obra = supabase_service.get_obra(data.obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    tasa_bcv = data.tasa_bcv or float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))

    # 1. Extracción con Gemini
    extracted = gemini_service.parse_audio_or_text_levantamiento(text_prompt=data.texto)
    raw_partidas = extracted.get("partidas", [])
    if not raw_partidas:
        raise HTTPException(status_code=400, detail="No se identificaron partidas en el texto proporcionado")

    partidas_input = [
        PartidaInput(
            tipo_partida=p.get("tipo_partida", "otro"),
            descripcion=p.get("descripcion"),
            largo=p.get("largo", 0.0),
            alto=p.get("alto", 0.0),
            cantidad=p.get("cantidad", 1.0),
            area=p.get("area", 0.0),
            unidad=p.get("unidad", "m2")
        )
        for p in raw_partidas
    ]

    # 2. Motor determinista
    presupuesto = ConstructionCalculator.procesar_presupuesto(partidas_input, tasa_bcv=tasa_bcv)

    # 3. Guardar en Supabase
    for p in presupuesto.partidas:
        p_dict = p.model_dump()
        p_dict["obra_id"] = data.obra_id
        supabase_service.save_partida(p_dict)

    hoja_items = [h.model_dump() for h in presupuesto.hoja_compras]
    supabase_service.save_hoja_compras(data.obra_id, hoja_items)

    supabase_service.update_obra(data.obra_id, {
        "presupuesto_total_usd": presupuesto.total_general_usd,
        "presupuesto_total_bs": presupuesto.total_general_bs,
        "tasa_bcv": tasa_bcv
    })

    return {
        "status": "success",
        "presupuesto": presupuesto,
        "obra_id": data.obra_id
    }

@router.post("/levantamiento/audio")
async def procesar_levantamiento_audio(
    obra_id: str = Form(...),
    audio: UploadFile = File(...)
):
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))

    audio_bytes = await audio.read()
    mime_type = audio.content_type or "audio/ogg"

    # 1. Extracción con Gemini
    extracted = gemini_service.parse_audio_or_text_levantamiento(
        audio_bytes=audio_bytes,
        mime_type=mime_type
    )
    raw_partidas = extracted.get("partidas", [])
    if not raw_partidas:
        raise HTTPException(status_code=400, detail="No se identificaron partidas en el audio")

    partidas_input = [
        PartidaInput(
            tipo_partida=p.get("tipo_partida", "otro"),
            descripcion=p.get("descripcion"),
            largo=p.get("largo", 0.0),
            alto=p.get("alto", 0.0),
            cantidad=p.get("cantidad", 1.0),
            area=p.get("area", 0.0),
            unidad=p.get("unidad", "m2")
        )
        for p in raw_partidas
    ]

    # 2. Motor determinista
    presupuesto = ConstructionCalculator.procesar_presupuesto(partidas_input, tasa_bcv=tasa_bcv)

    # 3. Guardar en Supabase
    for p in presupuesto.partidas:
        p_dict = p.model_dump()
        p_dict["obra_id"] = obra_id
        supabase_service.save_partida(p_dict)

    hoja_items = [h.model_dump() for h in presupuesto.hoja_compras]
    supabase_service.save_hoja_compras(obra_id, hoja_items)

    supabase_service.update_obra(obra_id, {
        "presupuesto_total_usd": presupuesto.total_general_usd,
        "presupuesto_total_bs": presupuesto.total_general_bs
    })

    return {
        "status": "success",
        "presupuesto": presupuesto,
        "obra_id": obra_id
    }

@router.get("/obras/{obra_id}/presupuesto/pdf")
def descargar_presupuesto_pdf(obra_id: str):
    """Genera y descarga en memoria el PDF formal del presupuesto de la obra según norma COVENIN."""
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    
    partidas = supabase_service.get_partidas(obra_id)
    tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
    precios_dict = supabase_service.get_catalogo_precios_dict()

    partidas_input = [
        PartidaInput(
            tipo_partida=p.get("tipo_partida", "otro"),
            descripcion=p.get("descripcion"),
            codigo_covenin=p.get("codigo_covenin"),
            largo=p.get("largo", 0.0),
            alto=p.get("alto", 0.0),
            cantidad=p.get("cantidad", 1.0),
            area=p.get("area", 0.0),
            unidad=p.get("unidad", "m2"),
            p_unit_usd_override=p.get("p_unit_usd")
        )
        for p in partidas
    ]
    pres = ConstructionCalculator.procesar_presupuesto(
        partidas_raw=partidas_input,
        tasa_bcv=tasa_bcv,
        precios_personalizados=precios_dict
    )
    from services.pdf_generator import PDFPresupuestoGenerator
    pdf_buf = PDFPresupuestoGenerator.generar_presupuesto_pdf(
        obra=obra,
        presupuesto=pres,
        codigo_presupuesto=f"OBX-PRE-{str(obra_id)[:8].upper()}"
    )
    import re
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', obra.get("nombre", "Obra"))[:25]
    return Response(
        content=pdf_buf.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Presupuesto_{clean_name}.pdf"
        }
    )

@router.get("/memoria-precios")
def get_memoria_precios(user_id: Optional[str] = None):
    """Devuelve los precios aprendidos de la memoria operativa del contratista."""
    return supabase_service.get_catalogo_precios(user_id=user_id)

@router.post("/memoria-precios")
def save_memoria_precio(data: MemoriaPrecioInput):
    """Guarda o actualiza un precio personalizado en la memoria operativa."""
    return supabase_service.save_catalogo_precio(data.model_dump())

@router.get("/obras/{obra_id}/historial-ediciones")
def get_historial_ediciones(obra_id: str):
    """Devuelve el historial de ediciones conversacionales del presupuesto."""
    return supabase_service.get_historial_ediciones(obra_id)

# ------------------------------------------------------------------------------
# COMPRAS Y FACTURAS (RESPALDO WEB TOTAL)
# ------------------------------------------------------------------------------
@router.get("/obras/{obra_id}/facturas")
def list_facturas(obra_id: str):
    return supabase_service.get_facturas(obra_id)

@router.post("/facturas/upload")
async def upload_factura_web(
    obra_id: str = Form(...),
    factura_img: UploadFile = File(...)
):
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")

    img_bytes = await factura_img.read()
    result = invoice_service.audit_and_process_invoice(
        image_bytes=img_bytes,
        obra_id=obra_id,
        filename=factura_img.filename or "factura_web.jpg"
    )
    return result

# ------------------------------------------------------------------------------
# AVANCE Y EVIDENCIAS
# ------------------------------------------------------------------------------
@router.get("/obras/{obra_id}/evidencias")
def list_evidencias(obra_id: str):
    return supabase_service.get_evidencias(obra_id)

@router.post("/evidencias/upload")
async def upload_evidencia_web(
    obra_id: str = Form(...),
    partida_id: Optional[str] = Form(None),
    porcentaje: float = Form(...),
    notas: Optional[str] = Form(""),
    foto: UploadFile = File(...)
):
    img_bytes = await foto.read()
    opt_bytes, mime = invoice_service.optimize_image(img_bytes)
    foto_url = supabase_service.upload_file(opt_bytes, filename=foto.filename or "evidencia.jpg", content_type=mime)

    if partida_id:
        supabase_service.update_partida_avance(partida_id, porcentaje)

    evidencia = supabase_service.save_evidencia({
        "obra_id": obra_id,
        "partida_id": partida_id or "",
        "porcentaje_alcanzado": porcentaje,
        "foto_url": foto_url,
        "notas": notas
    })
    return evidencia

# ------------------------------------------------------------------------------
# LIBRO DE OBRA, INCIDENCIAS Y RUTA PÚBLICA DE APROBACIÓN
# ------------------------------------------------------------------------------
@router.get("/obras/{obra_id}/libro-obra")
def list_libro_obra(obra_id: str):
    return supabase_service.get_libro_obra(obra_id)

@router.post("/incidencias/upload")
async def report_incidencia_web(
    obra_id: str = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(...),
    costo_adicional_usd: float = Form(0.0),
    foto: Optional[UploadFile] = File(None)
):
    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    
    img_bytes = None
    if foto:
        img_bytes = await foto.read()

    res = site_log_service.process_progress_or_incident(
        obra_id=obra_id,
        image_bytes=img_bytes,
        text_or_audio=f"{titulo}. {descripcion}",
        filename=foto.filename if foto else "incidencia.jpg"
    )
    return res

@router.get("/aprobar/{token_or_id}")
def get_incidencia_para_aprobar(token_or_id: str):
    """Ruta consultada por el frontend móvil en /aprobar/[id] para mostrar la ficha de daño oculto."""
    incidencia = supabase_service.get_incidencia_by_token(token_or_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia o token de aprobación no encontrado")
    
    obra = supabase_service.get_obra(incidencia.get("obra_id", ""))
    return {
        "incidencia": incidencia,
        "obra": obra
    }

@router.post("/aprobar/{token_or_id}")
async def ejecutar_aprobacion_cliente(token_or_id: str, data: AprobacionInput):
    """
    Ruta ejecutada cuando el cliente presiona 'Aprobar Adicional'.
    Cambia el estatus en vivo en Supabase y envía confirmación automática
    al chat de Telegram del ingeniero.
    """
    aprobada = supabase_service.aprobar_incidencia(token_or_id, cliente_nombre=data.cliente_nombre)
    if not aprobada:
        raise HTTPException(status_code=404, detail="No se pudo aprobar la incidencia")

    # Enviar notificación automática por Telegram si hay chat_id asociado
    chat_id = aprobada.get("telegram_chat_id")
    if chat_id:
        await telegram_bot.notificar_aprobacion_adicional(chat_id, aprobada)

    return {
        "status": "success",
        "message": "Adicional aprobado con éxito. Notificación enviada al contratista.",
        "incidencia": aprobada
    }

# ------------------------------------------------------------------------------
# TASA BCV OFICIAL Y SINCRONIZACIÓN
# ------------------------------------------------------------------------------
@router.get("/bcv")
def get_tasa_bcv_oficial():
    """Consulta la tasa oficial vigente del Banco Central de Venezuela (BCV)."""
    return bcv_service.get_tasa_oficial()

@router.post("/bcv/sincronizar/{obra_id}")
def sincronizar_tasa_bcv_obra(obra_id: str):
    """
    Sincroniza la obra activa con la Tasa Oficial del BCV en tiempo real
    y recalcula automáticamente los totales en Bolívares.
    """
    bcv_info = bcv_service.get_tasa_oficial()
    tasa = bcv_info.get("tasa_bcv", settings.TASA_BCV_DEFAULT)

    obra = supabase_service.get_obra(obra_id)
    if not obra:
        raise HTTPException(status_code=404, detail="Obra no encontrada")

    pres_usd = float(obra.get("presupuesto_total_usd", 0.0))
    gast_usd = float(obra.get("total_gastado_usd", 0.0))
    
    pres_bs = round(pres_usd * tasa, 2)
    gast_bs = round(gast_usd * tasa, 2)

    updated_obra = supabase_service.update_obra(obra_id, {
        "tasa_bcv": tasa,
        "presupuesto_total_bs": pres_bs,
        "total_gastado_bs": gast_bs
    })

    # También actualizar las partidas en Bolívares
    partidas = supabase_service.get_partidas(obra_id)
    for p in partidas:
        p_unit_usd = float(p.get("p_unit_usd", 0.0))
        total_usd = float(p.get("total_usd", 0.0))
        supabase_service.update_partida(p["id"], {
            "p_unit_bs": round(p_unit_usd * tasa, 2),
            "total_bs": round(total_usd * tasa, 2)
        })

    return {
        "status": "success",
        "tasa_bcv": tasa,
        "fuente": bcv_info.get("fuente"),
        "fecha": bcv_info.get("fecha"),
        "obra": updated_obra
    }

# ------------------------------------------------------------------------------
# SERVIR ARCHIVOS LOCALES EN CASO DE FALLBACK STORAGE
# ------------------------------------------------------------------------------
@router.get("/uploads/{filename}")
def get_uploaded_file(filename: str):
    safe_path = os.path.join("uploads", filename)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(safe_path)

# ------------------------------------------------------------------------------
# PERFILES TELEGRAM & VINCULACIÓN MULTIUSUARIO
# ------------------------------------------------------------------------------
class VincularRequest(BaseModel):
    codigo: str
    chat_id: str

@router.get("/perfil")
def get_perfil_usuario(user_id: Optional[str] = None, chat_id: Optional[str] = None):
    """Obtiene o inicializa el perfil con código de vinculación y API Key MCP."""
    if user_id:
        return supabase_service.get_or_create_perfil(user_id)
    if chat_id:
        p = supabase_service.get_perfil_by_chat_id(chat_id)
        if p:
            return p
    # Demo por defecto
    demo_id = "00000000-0000-0000-0000-000000000001"
    return supabase_service.get_or_create_perfil(demo_id)

@router.post("/perfil/vincular")
def vincular_telegram(data: VincularRequest):
    """Vincula un chat de Telegram mediante el código de 6 dígitos."""
    perfil = supabase_service.vincular_telegram_chat(data.codigo, data.chat_id)
    if not perfil:
        raise HTTPException(status_code=400, detail="Código de vinculación inválido o expirado")
    return {
        "status": "success",
        "message": "Chat de Telegram vinculado exitosamente.",
        "perfil": perfil
    }

class McpChatRequest(BaseModel):
    prompt: str
    api_key_mcp: Optional[str] = None

@router.post("/mcp/chat")
def mcp_chat_agent(req: McpChatRequest):
    """
    Ejecuta una consulta inteligente a Gemini conectada directamente con las herramientas del servidor MCP.
    Permite probar interactivamente el Agente IA desde la interfaz web o aplicaciones cliente.
    """
    from demo_gemini_mcp import procesar_consulta_gemini_mcp
    resultado = procesar_consulta_gemini_mcp(req.prompt, req.api_key_mcp)
    return resultado
