import re
import secrets
from typing import Dict, Any, Optional
from config import settings
from services.supabase_service import supabase_service
from services.gemini_service import gemini_service
from services.invoice_service import invoice_service

class SiteLogService:
    """
    Servicio para Libro de Obra, Registro de Avance de Partidas de la Cuadrilla y Daños Ocultos (Paradas).
    Calcula el % de variación contra el contrato base y el Avance Global Ponderado.
    """

    @staticmethod
    def render_progress_bar(percentage: float, length: int = 10) -> str:
        """Genera una barra visual en texto estilo [████████░░] 80% para Telegram."""
        pct = max(0.0, min(100.0, float(percentage)))
        filled = int(round((pct / 100.0) * length))
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {pct:.0f}%"

    @classmethod
    def calculate_global_progress(cls, obra_id: str) -> float:
        """Calcula el avance global ponderado por el costo de cada partida."""
        partidas = supabase_service.get_partidas(obra_id)
        if not partidas:
            return 0.0
        total_usd = sum(float(p.get("total_usd", 0.0)) for p in partidas)
        if total_usd <= 0:
            return 0.0
        avance_acumulado = sum(
            float(p.get("total_usd", 0.0)) * (float(p.get("porcentaje_avance", 0.0)) / 100.0)
            for p in partidas
        )
        return round((avance_acumulado / total_usd) * 100.0, 1)

    @classmethod
    def process_progress_or_incident(
        cls,
        obra_id: str,
        image_bytes: Optional[bytes] = None,
        text_or_audio: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        filename: str = "evidencia.jpg",
        chat_id: Optional[int] = None,
        responsable_nombre: str = "Cuadrilla de Campo"
    ) -> Dict[str, Any]:
        foto_url = ""
        if image_bytes:
            opt_bytes, mime = invoice_service.optimize_image(image_bytes)
            foto_url = supabase_service.upload_file(opt_bytes, filename=filename, content_type=mime)

        # Análisis con Gemini 2.5 Flash
        classified = gemini_service.parse_incident_or_progress(
            image_bytes=image_bytes,
            text_or_audio_prompt=text_or_audio,
            audio_bytes=audio_bytes
        )

        texto_lower = (text_or_audio or "").lower()
        es_dano_explicito = any(w in texto_lower for w in ["dano", "daño", "parada", "paro", "tuberia", "tubería", "filtracion", "filtración", "roto", "rota", "fuga", "oculto", "averia", "avería", "accidente"])

        # Una foto de campo sin daño explícito es SIEMPRE evidencia de avance
        if not es_dano_explicito and (image_bytes or classified.get("intencion") in ("avance_cuadrilla", "avance_obra", "levantamiento_nuevo")):
            tipo = "avance_obra"
        else:
            tipo = classified.get("tipo") or ("avance_obra" if classified.get("intencion") in ("avance_cuadrilla", "avance_obra") else classified.get("intencion", "avance_obra"))

        if tipo == "avance_cuadrilla":
            tipo = "avance_obra"

        obra = supabase_service.get_obra(obra_id) or {}
        presupuesto_base = float(obra.get("presupuesto_total_usd", 0.0))
        tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))

        # ----------------------------------------------------------------------
        # CASO 1: AVANCE DE OBRA SUBIDO POR LA CUADRILLA
        # ----------------------------------------------------------------------
        if tipo == "avance_obra":
            partida_ref = classified.get("partida_referencia")
            porcentaje = float(classified.get("porcentaje_alcanzado", 100.0))
            if text_or_audio:
                num_match = re.search(r"(\d{1,3})\s*%", text_or_audio)
                if num_match:
                    porcentaje = float(num_match.group(1))
            partidas = supabase_service.get_partidas(obra_id)
            
            target_partida = None
            if partida_ref:
                for p in partidas:
                    if p.get("tipo_partida") == partida_ref:
                        target_partida = p
                        break

            # Si no hubo coincidencia directa, buscar por sinónimos o descripción (ej. "moldear bloque", "pegar bloque" -> pared_bloque)
            if not target_partida and partidas:
                for p in partidas:
                    tipo_p = p.get("tipo_partida", "").lower()
                    desc_p = p.get("descripcion", "").lower()
                    if any(w in texto_lower for w in ["bloque", "pared", "friso", "moldear", "pegar", "albañileria", "albanileria"]) and ("bloque" in tipo_p or "bloque" in desc_p or "pared" in tipo_p):
                        target_partida = p
                        break
                    elif any(w in texto_lower for w in ["pintar", "pintura", "caucho", "esmalte"]) and ("pintura" in tipo_p or "pintar" in desc_p):
                        target_partida = p
                        break
                    elif any(w in texto_lower for w in ["ceramica", "cerámica", "porcelanato", "piso", "pego"]) and ("ceramica" in tipo_p or "piso" in desc_p or "ceramica" in desc_p):
                        target_partida = p
                        break
                    elif any(w in texto_lower for w in ["cielo", "raso", "drywall", "yeso"]) and ("cielo_raso" in tipo_p or "cielo" in desc_p):
                        target_partida = p
                        break
                    elif any(w in texto_lower for w in ["lampara", "lámpara", "led", "luminaria", "luz"]) and ("lampara" in tipo_p or "lampara" in desc_p):
                        target_partida = p
                        break

            if not target_partida and partidas:
                target_partida = partidas[0]

            if target_partida:
                supabase_service.update_partida_avance(target_partida["id"], porcentaje)
                evidencia = supabase_service.save_evidencia({
                    "partida_id": target_partida["id"],
                    "obra_id": obra_id,
                    "porcentaje_alcanzado": porcentaje,
                    "foto_url": foto_url or "https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?auto=format&fit=crop&w=600&q=80",
                    "notas": f"Reportado por {responsable_nombre}: {classified.get('descripcion', text_or_audio or 'Avance reportado por cuadrilla')}"
                })
                
                avance_global = cls.calculate_global_progress(obra_id)
                barra_partida = cls.render_progress_bar(porcentaje)
                barra_global = cls.render_progress_bar(avance_global)

                return {
                    "tipo": "avance_obra",
                    "partida": target_partida,
                    "porcentaje": porcentaje,
                    "avance_global": avance_global,
                    "barra_partida": barra_partida,
                    "barra_global": barra_global,
                    "responsable": responsable_nombre,
                    "foto_url": foto_url,
                    "evidencia": evidencia,
                    "mensaje": (
                        f"👷‍♂️ *¡AVANCE DE CUADRILLA REGISTRADO!*\n\n"
                        f"🏗️ *Obra:* {obra.get('nombre', 'Obra')}\n"
                        f"👤 *Reportó:* {responsable_nombre}\n"
                        f"📌 *Partida:* {target_partida.get('descripcion')}\n"
                        f"📈 *Avance Partida:* {barra_partida}\n"
                        f"🌐 *Avance Global Obra:* {barra_global}\n\n"
                        f"📸 *Evidencia:* Guardada en el expediente digital y sincronizada en tiempo real con el Dashboard.\n"
                        f"🔗 [Ver en Pantalla]({settings.FRONTEND_URL}/avance?obra_id={obra_id})"
                    )
                }
            else:
                avance_global = cls.calculate_global_progress(obra_id)
                return {
                    "tipo": "avance_obra",
                    "porcentaje": porcentaje,
                    "avance_global": avance_global,
                    "foto_url": foto_url,
                    "responsable": responsable_nombre,
                    "mensaje": f"👷‍♂️ Avance general registrado por {responsable_nombre}: {porcentaje:.0f}%."
                }

        # ----------------------------------------------------------------------
        # CASO 2: PARADA POR DAÑO OCULTO
        # ----------------------------------------------------------------------
        else:
            costo_extra_usd = float(classified.get("costo_adicional_usd", 0.0))
            if costo_extra_usd <= 0:
                costo_extra_usd = 250.0  # Estimación base mínima
            costo_extra_bs = round(costo_extra_usd * tasa_bcv, 2)

            # Cálculo de % variación sobre el contrato base
            if presupuesto_base > 0:
                pct_variacion = round((costo_extra_usd / presupuesto_base) * 100.0, 2)
            else:
                pct_variacion = 5.0

            token_aprobacion = secrets.token_urlsafe(12)
            link_aprobacion = f"{settings.FRONTEND_URL}/aprobar/{token_aprobacion}"

            incidencia_data = {
                "obra_id": obra_id,
                "tipo": "parada_dano_oculto",
                "titulo": classified.get("titulo", "Parada por daño oculto"),
                "descripcion": classified.get("descripcion", text_or_audio or "Se identificó daño imprevisto en la infraestructura."),
                "foto_url": foto_url or "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=800&q=80",
                "costo_adicional_usd": costo_extra_usd,
                "costo_adicional_bs": costo_extra_bs,
                "porcentaje_variacion": pct_variacion,
                "token_aprobacion": token_aprobacion,
                "estado_aprobacion": "pendiente",
                "cliente_nombre": obra.get("cliente", "Cliente de la Obra"),
                "telegram_chat_id": chat_id
            }

            saved = supabase_service.save_incidencia(incidencia_data)

            return {
                "tipo": "parada_dano_oculto",
                "incidencia": saved,
                "costo_adicional_usd": costo_extra_usd,
                "costo_adicional_bs": costo_extra_bs,
                "porcentaje_variacion": pct_variacion,
                "token_aprobacion": token_aprobacion,
                "link_aprobacion": link_aprobacion,
                "foto_url": foto_url,
                "mensaje": (
                    f"⚠️ *PARADA REGISTRADA POR LA CUADRILLA*\n\n"
                    f"📋 *Incidencia:* {saved['titulo']}\n"
                    f"📝 *Detalle:* {saved['descripcion']}\n\n"
                    f"💰 *Costo Adicional:* ${costo_extra_usd:.2f} (Bs. {costo_extra_bs:,.2f})\n"
                    f"📈 *Variación Contrato:* `+{pct_variacion:.2f}%`\n\n"
                    f"📲 *Enlace móvil para cliente:* {link_aprobacion}"
                )
            }

site_log_service = SiteLogService()
