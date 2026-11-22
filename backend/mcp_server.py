import sys
import os
import zlib
from typing import Dict, Any, List, Optional

# Asegurar que el directorio backend esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP, Context
from services.supabase_service import supabase_service
from services.calculator import (
    ConstructionCalculator, 
    PartidaInput, 
    CATALOGO_COVENIN, 
    PRECIOS_MATERIALES_BASE, 
    MANO_DE_OBRA_BASE
)
from services.bcv_service import bcv_service
from services.levantamiento_skill import levantamiento_skill
from services.site_log_service import site_log_service

# Inicializar servidor FastMCP
mcp = FastMCP("ObraExacta Operative Memory")

# ------------------------------------------------------------------------------
# RESOLUCIÓN Y VALIDACIÓN DE USUARIO (AISLAMIENTO POR API KEY)
# ------------------------------------------------------------------------------
def resolve_user_id(api_key_mcp: Optional[str] = None) -> str:
    """
    Resuelve el user_id correspondiente a la api_key_mcp proporcionada como parámetro
    o inyectada a través de headers HTTP (Authorization Bearer / X-API-Key).
    Garantiza aislamiento estricto multiusuario.
    """
    key = (api_key_mcp or "").strip()
    
    if not key:
        try:
            from fastmcp.server.dependencies import get_http_request
            req = get_http_request()
            if req:
                auth = req.headers.get("authorization", "").strip()
                if auth.lower().startswith("bearer "):
                    key = auth[7:].strip()
                elif auth:
                    key = auth
                if not key:
                    key = req.headers.get("x-api-key", "").strip()
                if not key:
                    key = req.query_params.get("api_key", "").strip() or req.query_params.get("api_key_mcp", "").strip()
        except Exception:
            pass

    if not key:
        raise ValueError(
            "Autenticación MCP requerida: proporcione 'api_key_mcp' como parámetro de la herramienta, "
            "o configure el header 'Authorization: Bearer <api_key_mcp>' en su cliente MCP."
        )

    perfil = supabase_service.get_perfil_by_api_key(key)
    if not perfil or not perfil.get("user_id"):
        raise ValueError(
            f"API Key '{key[:12]}...' inválida o no registrada en perfiles_telegram. "
            "Obtenga su API Key personal en el dashboard de ObraExacta (Menú Configuración / Perfil)."
        )

    return str(perfil["user_id"])


# ------------------------------------------------------------------------------
# HERRAMIENTA 1: LISTAR OBRAS DE USUARIO
# ------------------------------------------------------------------------------
@mcp.tool()
def listar_obras_usuario(api_key_mcp: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Devuelve las obras activas registradas, su presupuesto base contratado,
    el total gastado acumulado y el margen financiero disponible, aisladas
    exclusivamente para el usuario de la API Key.
    """
    user_id = resolve_user_id(api_key_mcp)
    obras = supabase_service.get_obras(user_id=user_id)
    res = []
    for o in obras:
        pres_usd = float(o.get("presupuesto_total_usd", 0.0))
        gast_usd = float(o.get("total_gastado_usd", 0.0))
        disp_usd = round(pres_usd - gast_usd, 2)
        margen_porc = round((disp_usd / pres_usd * 100.0), 2) if pres_usd > 0 else float(o.get("margen_meta", 30.0))
        res.append({
            "id": o.get("id"),
            "nombre": o.get("nombre"),
            "cliente": o.get("cliente"),
            "estado": o.get("estado", "activa"),
            "tasa_bcv": float(o.get("tasa_bcv", 918.77)),
            "presupuesto_total_usd": pres_usd,
            "presupuesto_total_bs": float(o.get("presupuesto_total_bs", 0.0)),
            "total_gastado_usd": gast_usd,
            "total_gastado_bs": float(o.get("total_gastado_bs", 0.0)),
            "disponible_usd": disp_usd,
            "margen_actual_porcentaje": margen_porc
        })
    return res


# ------------------------------------------------------------------------------
# HERRAMIENTA 2: CONSULTAR PRECIOS Y CATÁLOGO COVENIN
# ------------------------------------------------------------------------------
@mcp.tool()
def consultar_precios_y_covenin(api_key_mcp: Optional[str] = None) -> Dict[str, Any]:
    """
    Devuelve el catálogo oficial COVENIN de Venezuela y los precios unitarios
    personalizados aprendidos específicamente por ese contratista.
    """
    user_id = resolve_user_id(api_key_mcp)
    precios_usuario = supabase_service.get_catalogo_precios(user_id=user_id)
    precios_dict = supabase_service.get_catalogo_precios_dict(user_id=user_id)
    
    materiales_consolidados = {}
    for k, v in PRECIOS_MATERIALES_BASE.items():
        precio = precios_dict.get(k, v["p_unit_usd"])
        materiales_consolidados[k] = {
            "nombre": v["nombre"],
            "unidad": v["unidad"],
            "precio_usd": precio,
            "es_personalizado": k in precios_dict
        }

    return {
        "status": "success",
        "user_id": user_id,
        "total_precios_personalizados": len(precios_usuario),
        "precios_aprendidos_contratista": precios_usuario,
        "catalogo_covenin_oficial": CATALOGO_COVENIN,
        "materiales_vigentes": materiales_consolidados,
        "mano_de_obra_vigente": MANO_DE_OBRA_BASE
    }


# ------------------------------------------------------------------------------
# HERRAMIENTA 3: EVALUAR LEVANTAMIENTO TÉCNICO INCISIVO
# ------------------------------------------------------------------------------
@mcp.tool()
def evaluar_levantamiento(
    obra_nombre: str, 
    descripcion_trabajo: str, 
    api_key_mcp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evalúa un levantamiento técnico según la norma COVENIN usando el Loop Incisivo.
    Si faltan especificaciones críticas, devuelve preguntas aclaratorias cortas (máx 2)
    y si se requiere foto. Si está completo, genera el cálculo de presupuesto determinista.
    """
    user_id = resolve_user_id(api_key_mcp)
    
    # Asociar o crear obra en memoria/db
    obras = supabase_service.get_obras(user_id=user_id)
    obra_match = None
    for o in obras:
        if obra_nombre.lower() in str(o.get("nombre", "")).lower():
            obra_match = o
            break
            
    obra_id = obra_match.get("id") if obra_match else f"mcp-{user_id[:8]}"
    fake_chat_id = abs(zlib.crc32(f"{user_id}_{obra_nombre}".encode("utf-8"))) % 1000000000
    
    try:
        bcv_info = bcv_service.get_tasa_oficial()
        tasa_bcv = float(bcv_info.get("tasa_bcv", 918.77))
    except Exception:
        tasa_bcv = 918.77

    resp = levantamiento_skill.evaluar_o_acumular(
        chat_id=fake_chat_id,
        obra_id=str(obra_id),
        obra_nombre=obra_nombre,
        texto_usuario=descripcion_trabajo
    )

    if resp.estado == "necesita_aclaracion":
        return {
            "estado": "necesita_aclaracion",
            "obra_nombre": obra_nombre,
            "pregunta_corta": resp.pregunta_corta,
            "solicitar_foto": resp.solicitar_foto,
            "motivo": "Faltan especificaciones técnicas para cotizar con precisión según norma COVENIN.",
            "datos_acumulados": resp.datos_acumulados.model_dump()
        }
    else:
        partidas_calc = levantamiento_skill.convertir_a_partidas_calculator(resp.datos_acumulados)
        precios_dict = supabase_service.get_catalogo_precios_dict(user_id=user_id)
        presupuesto = ConstructionCalculator.procesar_presupuesto(
            partidas_raw=partidas_calc,
            tasa_bcv=tasa_bcv,
            precios_personalizados=precios_dict
        )
        return {
            "estado": "listo_para_presupuestar",
            "obra_nombre": obra_nombre,
            "tasa_bcv": tasa_bcv,
            "presupuesto_total_usd": presupuesto.total_general_usd,
            "presupuesto_total_bs": presupuesto.total_general_bs,
            "partidas": [p.model_dump() for p in presupuesto.partidas],
            "materiales_consolidados": [m.model_dump() for m in presupuesto.hoja_compras],
            "motivo_parada": resp.motivo_parada or "Levantamiento técnico completo bajo norma COVENIN."
        }


# ------------------------------------------------------------------------------
# HERRAMIENTA 4: OBTENER RESUMEN DE OBRA
# ------------------------------------------------------------------------------
@mcp.tool()
def obtener_resumen_obra(
    obra_nombre: str, 
    api_key_mcp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Devuelve las partidas, avances reportados por cuadrilla, gastos y variación de
    órdenes de trabajo adicionales de la obra especificada de ese contratista.
    """
    user_id = resolve_user_id(api_key_mcp)
    obras = supabase_service.get_obras(user_id=user_id)
    
    obra_match = None
    target_clean = obra_nombre.strip().lower()
    for o in obras:
        if target_clean in str(o.get("nombre", "")).strip().lower():
            obra_match = o
            break
            
    if not obra_match:
        nombres_disponibles = [o.get("nombre") for o in obras]
        raise ValueError(
            f"No se encontró la obra '{obra_nombre}' para este usuario. "
            f"Obras disponibles: {', '.join(filter(None, nombres_disponibles)) or 'Ninguna'}"
        )

    obra_id = obra_match["id"]
    partidas = supabase_service.get_partidas(obra_id)
    evidencias = supabase_service.get_evidencias(obra_id)
    facturas_gastos = supabase_service.get_facturas(obra_id)
    adicionales = supabase_service.get_libro_obra(obra_id)
    avance_global = site_log_service.calculate_global_progress(obra_id)

    pres_usd = float(obra_match.get("presupuesto_total_usd", 0.0))
    gast_usd = float(obra_match.get("total_gastado_usd", 0.0))
    disp_usd = round(pres_usd - gast_usd, 2)
    tasa_bcv = float(obra_match.get("tasa_bcv", 918.77))

    total_adicionales_usd = sum(float(a.get("costo_adicional_usd", 0.0)) for a in adicionales)
    pct_variacion = round((total_adicionales_usd / pres_usd * 100.0), 2) if pres_usd > 0 else 0.0

    return {
        "status": "success",
        "obra": {
            "id": obra_id,
            "nombre": obra_match.get("nombre"),
            "cliente": obra_match.get("cliente"),
            "estado": obra_match.get("estado", "activa"),
            "avance_global_ponderado_porcentaje": avance_global,
            "barra_avance": site_log_service.render_progress_bar(avance_global),
            "presupuesto_total_usd": pres_usd,
            "presupuesto_total_bs": round(pres_usd * tasa_bcv, 2),
            "total_gastado_usd": gast_usd,
            "total_gastado_bs": round(gast_usd * tasa_bcv, 2),
            "disponible_usd": disp_usd,
            "tasa_bcv": tasa_bcv
        },
        "partidas": partidas,
        "avances_cuadrilla": evidencias,
        "gastos_y_facturas": facturas_gastos,
        "adicionales_y_paradas": adicionales,
        "resumen_variacion": {
            "total_adicionales_usd": round(total_adicionales_usd, 2),
            "total_adicionales_bs": round(total_adicionales_usd * tasa_bcv, 2),
            "porcentaje_variacion_acumulado": pct_variacion
        }
    }


# ------------------------------------------------------------------------------
# EJECUCIÓN DIRECTA COMO SERVIDOR INDEPENDIENTE
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ObraExacta FastMCP Server")
    parser.add_argument("--transport", default="sse", choices=["sse", "stdio"], help="Transporte de comunicación")
    parser.add_argument("--host", default="0.0.0.0", help="Host del servidor HTTP/SSE")
    parser.add_argument("--port", type=int, default=8001, help="Puerto del servidor HTTP/SSE")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"Iniciando ObraExacta MCP Server en http://{args.host}:{args.port}/sse ...")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Iniciando ObraExacta MCP Server en stdio...")
        mcp.run(transport="stdio")
