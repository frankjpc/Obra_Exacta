import sys
import os
import json
import httpx
from typing import Optional, Dict, Any

# Asegurar path backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from mcp_server import (
    listar_obras_usuario,
    consultar_precios_y_covenin,
    evaluar_levantamiento,
    obtener_resumen_obra,
    resolve_user_id
)
from services.supabase_service import supabase_service

DEMO_KEY = "obx_mcp_demo_7f8a9b2c3d4e5f6a7b8c9d0e"

TOOLS_DECLARATIONS = [
    {
        "name": "listar_obras_usuario",
        "description": "Devuelve la lista de obras activas, presupuestos, gastos y margen financiero disponible del contratista.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "consultar_precios_y_covenin",
        "description": "Devuelve el catálogo de partidas oficiales COVENIN de Venezuela y los precios aprendidos de materiales y mano de obra.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "evaluar_levantamiento",
        "description": "Evalúa un levantamiento técnico de obra. Si faltan medidas o datos, devuelve preguntas de campo; si está completo, calcula el presupuesto exacto según norma COVENIN.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "obra_nombre": {"type": "STRING", "description": "Nombre de la obra"},
                "descripcion_trabajo": {"type": "STRING", "description": "Detalle técnico de los trabajos a realizar"}
            },
            "required": ["obra_nombre", "descripcion_trabajo"]
        }
    },
    {
        "name": "obtener_resumen_obra",
        "description": "Devuelve el informe completo de una obra: partidas, avance por cuadrilla, facturas de compras, y órdenes de trabajo adicionales por daños ocultos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "obra_nombre": {"type": "STRING", "description": "Nombre de la obra a consultar"}
            },
            "required": ["obra_nombre"]
        }
    }
]

def ejecutar_herramienta_local(tool_name: str, args: dict, api_key_mcp: Optional[str] = None) -> dict:
    """Ejecuta deterministamente la herramienta en el backend usando la clave del usuario o la demo."""
    key = api_key_mcp or DEMO_KEY
    if tool_name == "listar_obras_usuario":
        res = listar_obras_usuario(api_key_mcp=key)
        return {"obras": res}
    elif tool_name == "consultar_precios_y_covenin":
        return consultar_precios_y_covenin(api_key_mcp=key)
    elif tool_name == "evaluar_levantamiento":
        return evaluar_levantamiento(
            obra_nombre=args.get("obra_nombre", "Obra Principal"),
            descripcion_trabajo=args.get("descripcion_trabajo", ""),
            api_key_mcp=key
        )
    elif tool_name == "obtener_resumen_obra":
        return obtener_resumen_obra(
            obra_nombre=args.get("obra_nombre", "Obra Principal"),
            api_key_mcp=key
        )
    else:
        return {"error": f"Herramienta '{tool_name}' no encontrada"}


def procesar_consulta_gemini_mcp(prompt_usuario: str, api_key_mcp: Optional[str] = None) -> Dict[str, Any]:
    """
    Ejecuta el ciclo completo de agente:
    Prompt -> Gemini -> Decisión de Herramienta MCP -> Ejecución Determinista en ObraExacta -> Respuesta Final.
    """
    api_key = settings.GEMINI_API_KEY
    key_mcp = api_key_mcp or DEMO_KEY
    if not api_key:
        return {
            "status": "error",
            "message": "GEMINI_API_KEY no configurada",
            "response": "Error: GEMINI_API_KEY no configurada en el servidor."
        }

    model_name = "gemini-3.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt_usuario}]
            }
        ],
        "tools": [
            {
                "functionDeclarations": TOOLS_DECLARATIONS
            }
        ],
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Eres el Asistente Técnico y Financiero de ObraExacta para ingenieros y contratistas. "
                        "Usa siempre las herramientas MCP de ObraExacta para consultar datos reales de obras, "
                        "catálogos COVENIN y presupuestos. NUNCA inventes números ni nombres de obras. "
                        "Responde de forma ejecutiva, técnica, concisa y profesional con montos en USD y Bs."
                    )
                }
            ]
        }
    }

    try:
        with httpx.Client(timeout=35.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "response": f"Error comunicando con Gemini ({resp.status_code}): {resp.text}"
                }

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return {"status": "error", "response": "Sin respuesta de Gemini."}

            parts = candidates[0].get("content", {}).get("parts", [])
            call = None
            for p in parts:
                if "functionCall" in p:
                    call = p["functionCall"]
                    break

            if not call:
                texto = "".join(p.get("text", "") for p in parts)
                return {
                    "status": "success",
                    "tool_called": None,
                    "tool_args": {},
                    "tool_result": {},
                    "response": texto
                }

            tool_name = call.get("name")
            tool_args = call.get("args", {})
            tool_result = ejecutar_herramienta_local(tool_name, tool_args, api_key_mcp=key_mcp)

            payload["contents"].append(candidates[0]["content"])
            payload["contents"].append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {
                                "content": tool_result
                            }
                        }
                    }
                ]
            })

            resp2 = client.post(url, json=payload)
            if resp2.status_code == 200:
                data2 = resp2.json()
                cands2 = data2.get("candidates", [])
                final_text = "".join(p.get("text", "") for p in cands2[0].get("content", {}).get("parts", [])) if cands2 else "Operación completada."
                return {
                    "status": "success",
                    "tool_called": tool_name,
                    "tool_args": tool_args,
                    "tool_result": tool_result,
                    "response": final_text
                }
            else:
                return {
                    "status": "error",
                    "tool_called": tool_name,
                    "tool_result": tool_result,
                    "response": f"Error en síntesis final ({resp2.status_code})"
                }
    except Exception as e:
        return {"status": "error", "response": f"Excepción ejecutando agente: {str(e)}"}


if __name__ == "__main__":
    pregunta = sys.argv[1] if len(sys.argv) > 1 else "¿Cuáles son las obras activas que tengo y cuánto dinero me queda disponible?"
    print(f"\n👤 USUARIO PREGUNTA: \"{pregunta}\"")
    res = procesar_consulta_gemini_mcp(pregunta)
    print(f"\n🛠️ HERRAMIENTA MCP INVOCADA: {res.get('tool_called')}")
    print(f"\n📋 RESPUESTA DE GEMINI:\n{res.get('response')}\n")
