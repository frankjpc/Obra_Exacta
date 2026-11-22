import json
import re
import base64
import httpx
from typing import Dict, Any, List, Optional
from config import settings

class GeminiService:
    """
    Servicio de integración con Gemini vía REST API con httpx.
    Gemini NUNCA calcula matemáticas ni rendimientos;
    SOLO extrae parámetros estructurados en JSON estricto a partir de:
    - Notas de voz (.ogg) o texto de levantamiento
    - Reportes de avance de obra enviados por la cuadrilla de campo
    - Fotos de facturas de ferretería
    - Reportes de averías o paradas por daño oculto
    """
    CANDIDATE_MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash"
    ]

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.active_model = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        if not self.api_key:
            print("GEMINI_API_KEY no configurado. Se usará el parser heurístico de respaldo.")
        else:
            print(f"GeminiService configurado con modelo prioritario: {self.active_model}")

    @property
    def client(self):
        return bool(self.api_key)

    def _call_gemini_rest(
        self,
        parts: List[Dict[str, Any]],
        system_instruction: str,
        response_mime_type: str = "application/json"
    ) -> Optional[str]:
        """
        Ejecuta la llamada a la REST API de Google Generative Language con reintentos en cascada.
        Usa un timeout generoso de 35s adecuado para transcripción de audio e imágenes.
        """
        if not self.api_key:
            return None

        # Priorizar modelos activos verificados
        models = [self.active_model] + [m for m in self.CANDIDATE_MODELS if m != self.active_model]
        seen = set()
        models = [m for m in models if m and not (m in seen or seen.add(m))]

        payload = {
            "contents": [{
                "parts": parts
            }],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "responseMimeType": response_mime_type,
                "temperature": 0.1
            }
        }

        last_err = None
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                with httpx.Client(timeout=35.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if part_text:
                                self.active_model = model
                                return part_text.strip()
                    elif resp.status_code == 404:
                        continue
                    elif resp.status_code == 400:
                        print(f"Aviso Gemini (HTTP 400 formato): {resp.text[:120]}")
                        last_err = resp.text
                        break
                    else:
                        print(f"Aviso Gemini ({model} HTTP {resp.status_code}): {resp.text[:120]}")
                        last_err = resp.text
            except Exception as e:
                last_err = e
                print(f"Error de conexión con Gemini ({model}): {e}")

        if last_err:
            print(f"Fallo en llamada a Gemini: {last_err}.")
        return None

    def process_audio_or_field_message(
        self,
        audio_bytes: Optional[bytes] = None,
        text_prompt: Optional[str] = None,
        mime_type: str = "audio/ogg"
    ) -> Dict[str, Any]:
        """
        PROCESAMIENTO UNIFICADO EN UN SOLO PASO (1 llamada en vez de 2):
        Clasifica la intención del audio o texto (levantamiento, avance de cuadrilla, parada/daño)
        y extrae simultáneamente todas las partidas y parámetros necesarios.
        """
        system_instruction = (
            "Eres el copiloto experto en ingeniería civil y obras de construcción en Venezuela de ObraExacta. "
            "Escucha atentamente el audio o lee el texto en español (considerando términos comunes de construcción en Venezuela como friso, bloque de 15, tabiquería, pego, porcelanato, drywall, cielo raso, etc.). "
            "Clasifica la intención en:\n"
            "1. 'levantamiento_nuevo': Si dictan dimensiones, medidas o partidas para cotizar o presupuestar (ej. 'Pared de 4x2.80', '50 m2 de pintura', '10 lámparas').\n"
            "2. 'avance_cuadrilla': Si la cuadrilla o el maestro reporta progreso físico (ej. 'Terminamos el friso al 80%', 'Listas las lámparas', 'Colocado el piso').\n"
            "3. 'parada_dano_oculto': Si reportan averías, tuberías rotas, daño eléctrico o paralización imprevista.\n"
            "4. 'editar_presupuesto': Si piden cambiar, editar, subir o bajar el precio unitario, o modificar la cantidad de un material o partida en el presupuesto (ej. 'cámbiale el precio de la pintura a 8 dólares el metro', 'sube el bloque a 1.35 con Ferretería Los Guayos', 'agrega 4 lámparas más al último presupuesto', 'pon la cerámica en 18').\n\n"
            "NUNCA calcules costos ni precios; solo extrae dimensiones, cantidades y datos técnicos.\n"
            "Devuelve ÚNICAMENTE un objeto JSON válido con este formato:\n"
            "{\n"
            '  "intencion": "levantamiento_nuevo" | "avance_cuadrilla" | "parada_dano_oculto" | "editar_presupuesto",\n'
            '  "edicion": {\n'
            '    "accion": "modificar_precio" | "modificar_cantidad" | "agregar_partida",\n'
            '    "tipo_objetivo": "material" | "partida" | "mano_de_obra",\n'
            '    "partida_o_material": "bloque_15cm" | "arena_lavada" | "cemento_gris" | "pintura_caucho" | "ceramica_piso" | "pego_gris" | "lamina_drywall" | "perfileria_cielo" | "lampara_led" | "cable_conectores" | "pared_bloque" | "pintura" | "ceramica" | "cielo_raso" | "lampara" | "otro",\n'
            '    "nombre_referencia": "Nombre legible del ítem a modificar",\n'
            '    "nuevo_valor": 0.0,\n'
            '    "unidad": "m2" | "piezas" | "galones" | "sacos" | "m3" | "und",\n'
            '    "proveedor": "Nombre de la ferretería o proveedor si se menciona, o null"\n'
            '  },\n'
            '  "partida_referencia": "pared_bloque" | "pintura" | "ceramica" | "cielo_raso" | "lampara" | null,\n'
            '  "porcentaje_alcanzado": 0.0,\n'
            '  "titulo": "Título conciso del reporte o levantamiento",\n'
            '  "descripcion": "Detalle técnico de lo dictado o ejecutado",\n'
            '  "costo_adicional_usd": 0.0,\n'
            '  "tiempo_retraso_horas": 0,\n'
            '  "partidas": [\n'
            "    {\n"
            '      "tipo_partida": "pared_bloque" | "pintura" | "ceramica" | "cielo_raso" | "lampara" | "otro",\n'
            '      "descripcion": "Descripción concisa de la partida",\n'
            '      "largo": 0.0,\n'
            '      "alto": 0.0,\n'
            '      "cantidad": 1.0,\n'
            '      "area": 0.0,\n'
            '      "unidad": "m2" | "piezas" | "ml" | "und"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        parts = []
        if audio_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(audio_bytes).decode("utf-8")
                }
            })
            if text_prompt:
                parts.append({"text": text_prompt})
            else:
                parts.append({"text": "Escucha y transcribe fielmente las medidas y partidas de construcción dictadas en este audio."})
        elif text_prompt:
            parts.append({"text": text_prompt})

        res_text = self._call_gemini_rest(parts, system_instruction)
        if res_text:
            try:
                cleaned = re.sub(r"^```json\s*", "", res_text)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                print(f"Error decodificando respuesta unificada JSON: {e}")

        # Si falló la llamada remota y había texto, usar el analizador heurístico del texto real
        if text_prompt:
            return self._heuristic_levantamiento_parser(text_prompt)

        # Si era audio y falló la conexión remota, NO inyectar datos genéricos falsos
        return {
            "intencion": "levantamiento_nuevo",
            "partidas": [],
            "error": "No se pudo interpretar el audio con Gemini debido a problemas de conexión. Por favor reenvía el audio o escribe las medidas por texto."
        }

    def classify_audio_intent(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> Dict[str, Any]:
        """Wrapper de compatibilidad."""
        res = self.process_audio_or_field_message(audio_bytes=audio_bytes, mime_type=mime_type)
        return {"intencion": res.get("intencion", "levantamiento_nuevo")}

    def parse_audio_or_text_levantamiento(
        self, 
        audio_bytes: Optional[bytes] = None, 
        text_prompt: Optional[str] = None,
        mime_type: str = "audio/ogg"
    ) -> Dict[str, Any]:
        """Wrapper de compatibilidad."""
        res = self.process_audio_or_field_message(audio_bytes=audio_bytes, text_prompt=text_prompt, mime_type=mime_type)
        return res

    def parse_hardware_invoice(
        self, 
        image_bytes: bytes, 
        mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """
        Extrae proveedor, nro de control, fecha, total_usd, total_bs y lista de ítems de una foto de factura de ferretería.
        """
        system_instruction = (
            "Eres un auditor contable experto en ferreterías y compras de construcción en Venezuela. "
            "Analiza con extremo cuidado la foto de la factura o recibo. Extrae los datos fiscales y cada material comprado con su precio. "
            "Devuelve ÚNICAMENTE un JSON con este formato exacto:\n"
            "{\n"
            '  "proveedor": "Nombre de la ferretería o negocio",\n'
            '  "nro_control": "Número de factura o control fiscal",\n'
            '  "fecha": "YYYY-MM-DD",\n'
            '  "total_usd": 0.0,\n'
            '  "total_bs": 0.0,\n'
            '  "items": [\n'
            "    {\n"
            '      "descripcion": "Descripción del ítem o material",\n'
            '      "cantidad": 1.0,\n'
            '      "precio_unitario_usd": 0.0,\n'
            '      "total_usd": 0.0\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        parts = [
            {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(image_bytes).decode("utf-8")
                }
            },
            {"text": "Extrae todos los ítems, proveedor y montos de esta factura de ferretería."}
        ]

        res_text = self._call_gemini_rest(parts, system_instruction)
        if res_text:
            try:
                cleaned = re.sub(r"^```json\s*", "", res_text)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                print(f"Error decodificando factura JSON: {e}")

        # En caso de no poder leer la imagen, reportar error explícito en lugar de inventar una ferretería ficticia
        return {
            "error": "No se pudieron identificar ítems ni montos fiscales legibles en la imagen.",
            "proveedor": "Proveedor no identificado",
            "nro_control": "S/N",
            "fecha": "Hoy",
            "total_usd": 0.0,
            "total_bs": 0.0,
            "items": []
        }

    def parse_incident_or_progress(
        self, 
        image_bytes: Optional[bytes] = None, 
        text_or_audio_prompt: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """Wrapper de compatibilidad para incidencias y avances."""
        res = self.process_audio_or_field_message(audio_bytes=audio_bytes, text_prompt=text_or_audio_prompt)
        return res

    def _heuristic_levantamiento_parser(self, text: str) -> Dict[str, Any]:
        """Analizador heurístico aplicado ÚNICAMENTE sobre texto real enviado por el usuario."""
        lower = text.lower()

        # Detección heurística de edición conversacional de precios o cantidades
        if any(w in lower for w in ["cambia", "cámbiale", "sube", "baja", "ajusta", "pon el", "pon la", "precio de", "dólares", "dolares", "$"]):
            # Buscar número (precio o cantidad)
            num_match = re.search(r"(\d+(?:\.\d+)?)", lower)
            nuevo_val = float(num_match.group(1)) if num_match else 0.0

            # Detectar proveedor si se menciona ferretería
            prov_match = re.search(r"(?:con|en|de)\s+(ferreter[ií]a\s+[a-zA-Z0-9_\s]+|materiales\s+[a-zA-Z0-9_\s]+)", lower)
            proveedor = prov_match.group(1).title() if prov_match else None

            if "pintura" in lower:
                return {
                    "intencion": "editar_presupuesto",
                    "edicion": {
                        "accion": "modificar_precio",
                        "tipo_objetivo": "material",
                        "partida_o_material": "pintura_caucho",
                        "nombre_referencia": "Pintura de caucho profesional",
                        "nuevo_valor": nuevo_val,
                        "unidad": "m2" if "metro" in lower or "m2" in lower else "galones",
                        "proveedor": proveedor
                    }
                }
            elif "bloque" in lower or "pared" in lower:
                return {
                    "intencion": "editar_presupuesto",
                    "edicion": {
                        "accion": "modificar_precio",
                        "tipo_objetivo": "material",
                        "partida_o_material": "bloque_15cm",
                        "nombre_referencia": "Bloque de cemento/arcilla 15cm",
                        "nuevo_valor": nuevo_val,
                        "unidad": "piezas",
                        "proveedor": proveedor
                    }
                }
            elif "l[aá]mpara" in lower or "led" in lower:
                es_cantidad = any(w in lower for w in ["agrega", "suma", "más", "mas", "piezas", "unidades"])
                return {
                    "intencion": "editar_presupuesto",
                    "edicion": {
                        "accion": "modificar_cantidad" if es_cantidad else "modificar_precio",
                        "tipo_objetivo": "partida",
                        "partida_o_material": "lampara",
                        "nombre_referencia": "Luminaria LED Panel",
                        "nuevo_valor": nuevo_val,
                        "unidad": "piezas",
                        "proveedor": proveedor
                    }
                }
            elif "cer[aá]mica" in lower or "porcelanato" in lower:
                return {
                    "intencion": "editar_presupuesto",
                    "edicion": {
                        "accion": "modificar_precio",
                        "tipo_objetivo": "material",
                        "partida_o_material": "ceramica_piso",
                        "nombre_referencia": "Cerámica esmaltada",
                        "nuevo_valor": nuevo_val,
                        "unidad": "m2",
                        "proveedor": proveedor
                    }
                }

        partidas = []

        if "pared" in lower or "bloque" in lower or "tabique" in lower:
            largo, alto = 6.0, 2.6
            dims = re.findall(r"(\d+(?:\.\d+)?)\s*(?:m|metros)?\s*(?:de\s*)?(?:largo|ancho|x)?.*?(\d+(?:\.\d+)?)\s*(?:m|metros)?\s*(?:de\s*)?(?:alto)?", lower)
            if dims:
                try:
                    largo = float(dims[0][0])
                    alto = float(dims[0][1])
                except Exception:
                    pass
            partidas.append({
                "tipo_partida": "pared_bloque",
                "descripcion": f"Pared de bloque ({largo}m x {alto}m)",
                "largo": largo,
                "alto": alto,
                "cantidad": 1.0,
                "area": round(largo * alto, 2),
                "unidad": "m2"
            })

        if "pintura" in lower or "pintar" in lower:
            area = 50.0
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|metros cuadrados)", lower)
            if match:
                area = float(match.group(1))
            partidas.append({
                "tipo_partida": "pintura",
                "descripcion": f"Pintura de caucho ({area} m²)",
                "largo": 0.0,
                "alto": 0.0,
                "cantidad": 1.0,
                "area": area,
                "unidad": "m2"
            })

        if "ceramica" in lower or "cerámica" in lower or "piso" in lower:
            area = 35.0
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|metros cuadrados)", lower)
            if match:
                area = float(match.group(1))
            partidas.append({
                "tipo_partida": "ceramica",
                "descripcion": f"Revestimiento cerámico ({area} m²)",
                "largo": 0.0,
                "alto": 0.0,
                "cantidad": 1.0,
                "area": area,
                "unidad": "m2"
            })

        if "cielo" in lower or "drywall" in lower or "techo" in lower:
            partidas.append({
                "tipo_partida": "cielo_raso",
                "descripcion": "Cielo raso suspendido",
                "largo": 0.0,
                "alto": 0.0,
                "cantidad": 1.0,
                "area": 40.0,
                "unidad": "m2"
            })

        if "lampara" in lower or "lámpara" in lower or "led" in lower:
            cant = 12.0
            match = re.search(r"(\d+)\s*(?:lamparas|lámparas|piezas|luces|focos|luminarias)", lower)
            if match:
                cant = float(match.group(1))
            partidas.append({
                "tipo_partida": "lampara",
                "descripcion": f"Luminarias LED ({cant:.0f} piezas)",
                "largo": 0.0,
                "alto": 0.0,
                "cantidad": cant,
                "area": cant,
                "unidad": "piezas"
            })

        return {
            "intencion": "levantamiento_nuevo",
            "partidas": partidas
        }

gemini_service = GeminiService()
