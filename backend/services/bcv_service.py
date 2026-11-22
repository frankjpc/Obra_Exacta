import httpx
from typing import Dict, Any, Optional
from config import settings

class BCVService:
    """
    Servicio para consultar la Tasa Oficial del Banco Central de Venezuela (BCV).
    Utiliza APIs públicas directas con reintentos y fallback determinista.
    """
    ENDPOINTS = [
        "https://ve.dolarapi.com/v1/dolares/oficial",
        "https://pydolarve.org/api/v1/dollar?page=bcv"
    ]

    @classmethod
    def get_tasa_oficial(cls) -> Dict[str, Any]:
        """Consulta la tasa oficial vigente del BCV en tiempo real."""
        headers = {"User-Agent": "ObraExacta/1.0 (Construction Bot)"}
        for url in cls.ENDPOINTS:
            try:
                with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Formato dolarapi.com: {"promedio": 918.7662, "fechaActualizacion": ...}
                        if "promedio" in data and data["promedio"] > 0:
                            tasa = float(data["promedio"])
                            fecha = data.get("fechaActualizacion", "Hoy")
                            return {
                                "status": "success",
                                "tasa_bcv": round(tasa, 2),
                                "tasa_exacta": tasa,
                                "fuente": "Banco Central de Venezuela (BCV)",
                                "fecha": fecha
                            }
                        # Formato pydolarve.org
                        elif "monitors" in data and "bcv" in data["monitors"]:
                            tasa = float(data["monitors"]["bcv"].get("price", settings.TASA_BCV_DEFAULT))
                            return {
                                "status": "success",
                                "tasa_bcv": round(tasa, 2),
                                "tasa_exacta": tasa,
                                "fuente": "BCV (PyDolar)",
                                "fecha": data["monitors"]["bcv"].get("last_update", "Hoy")
                            }
            except Exception as e:
                print(f"Aviso al consultar tasa BCV en {url}: {e}")

        # Fallback a la tasa por defecto configurada
        return {
            "status": "fallback",
            "tasa_bcv": settings.TASA_BCV_DEFAULT,
            "tasa_exacta": settings.TASA_BCV_DEFAULT,
            "fuente": "Tasa Configurada en Sistema",
            "fecha": "Offline"
        }

bcv_service = BCVService()
