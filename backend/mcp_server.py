import sys
import os
from typing import Dict, Any, List, Optional

# Asegurar que el directorio backend esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server.mcpserver import MCPServer
    FastMCP = MCPServer
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        from mcp.server import Server as FastMCP

from services.supabase_service import supabase_service
from services.calculator import (
    ConstructionCalculator, 
    PartidaInput, 
    CATALOGO_COVENIN, 
    PRECIOS_MATERIALES_BASE, 
    MANO_DE_OBRA_BASE
)
from services.bcv_service import bcv_service

# Inicializar servidor MCP ligero
mcp = FastMCP("ObraExacta Operative Memory")

# ------------------------------------------------------------------------------
# HERRAMIENTA 1: CONSULTAR CATÁLOGO DE PRECIOS Y MEMORIA OPERATIVA
# ------------------------------------------------------------------------------
@mcp.tool()
def consultar_catalogo_precios() -> Dict[str, Any]:
    """
    Devuelve los precios unitarios y materiales guardados en la memoria operativa del contratista,
    junto con los códigos oficiales de la Norma COVENIN Venezuela.
    """
    precios_usuario = supabase_service.get_catalogo_precios()
    precios_dict = supabase_service.get_catalogo_precios_dict()
    
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
        "total_precios_personalizados": len(precios_usuario),
        "precios_aprendidos_contratista": precios_usuario,
        "catalogo_covenin_oficial": CATALOGO_COVENIN,
        "materiales_vigentes": materiales_consolidados,
        "mano_de_obra_vigente": MANO_DE_OBRA_BASE
    }

# ------------------------------------------------------------------------------
# HERRAMIENTA 2: LISTAR OBRAS Y MÁRGENES FINANCIEROS
# ------------------------------------------------------------------------------
@mcp.tool()
def listar_obras_y_margenes() -> List[Dict[str, Any]]:
    """
    Devuelve las obras activas registradas, su presupuesto base contratado,
    el total gastado real acumulado en facturas y el margen financiero disponible.
    """
    obras = supabase_service.get_obras()
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
# HERRAMIENTA 3: CALCULAR PARTIDA SEGÚN NORMA COVENIN Y MEMORIA OPERATIVA
# ------------------------------------------------------------------------------
@mcp.tool()
def calcular_partida_covenin(
    tipo_partida: str,
    largo: float = 0.0,
    alto: float = 0.0,
    cantidad: float = 1.0,
    area: float = 0.0
) -> Dict[str, Any]:
    """
    Ejecuta el cálculo determinista exacto de una partida de construcción según la norma COVENIN,
    aplicando automáticamente la memoria de precios unitarios personalizada del contratista y
    la tasa oficial BCV del día.
    """
    try:
        bcv_info = bcv_service.get_tasa_oficial()
        tasa_bcv = float(bcv_info.get("tasa_bcv", 918.77))
    except Exception:
        tasa_bcv = 918.77

    precios_dict = supabase_service.get_catalogo_precios_dict()
    partida_in = PartidaInput(
        tipo_partida=tipo_partida,
        largo=largo,
        alto=alto,
        cantidad=cantidad,
        area=area
    )
    calc = ConstructionCalculator.calcular_partida(
        item=partida_in,
        tasa_bcv=tasa_bcv,
        precios_personalizados=precios_dict
    )
    return {
        "status": "success",
        "codigo_covenin": calc.codigo_covenin,
        "tipo_partida": calc.tipo_partida,
        "descripcion": calc.descripcion,
        "unidad": calc.unidad,
        "cantidad": calc.cantidad,
        "area": calc.area,
        "p_unit_usd": calc.p_unit_usd,
        "total_usd": calc.total_usd,
        "tasa_bcv": tasa_bcv,
        "p_unit_bs": calc.p_unit_bs,
        "total_bs": calc.total_bs,
        "costo_materiales_usd": calc.costo_materiales_usd,
        "costo_mano_obra_usd": calc.costo_mano_obra_usd,
        "materiales": [m.model_dump() for m in calc.materiales]
    }

if __name__ == "__main__":
    print("Iniciando ObraExacta MCP Server en stdio...")
    mcp.run()
