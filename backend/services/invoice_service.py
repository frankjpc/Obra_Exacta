import io
import hashlib
from typing import Dict, Any, Tuple, List
from PIL import Image
from config import settings
from services.supabase_service import supabase_service
from services.gemini_service import gemini_service
from services.calculator import PRECIOS_MATERIALES_BASE

class InvoiceService:
    """
    Servicio de procesamiento de facturas de ferretería:
    1. Optimización en memoria con Pillow
    2. Hash SHA-256 anti-duplicados
    3. Extracción estructurada con Gemini 2.5 Flash
    4. Auditoría de sobreprecio y materiales fuera de partida
    5. Deducción presupuestaria y cálculo de margen restante
    """

    @staticmethod
    def optimize_image(image_bytes: bytes, max_dim: int = 1600, quality: int = 85) -> Tuple[bytes, str]:
        """
        Optimiza la imagen en memoria con Pillow para minimizar el uso de RAM y almacenamiento.
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            w, h = img.size
            if max(w, h) > max_dim:
                ratio = max_dim / float(max(w, h))
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
            return output_buffer.getvalue(), "image/jpeg"
        except Exception as e:
            print(f"Aviso Pillow: {e}. Usando bytes originales.")
            return image_bytes, "image/jpeg"

    @staticmethod
    def compute_sha256(image_bytes: bytes) -> str:
        """Calcula el hash criptográfico SHA-256 para prevenir fraude por doble facturación."""
        return hashlib.sha256(image_bytes).hexdigest()

    @classmethod
    def audit_and_process_invoice(
        cls, 
        image_bytes: bytes, 
        obra_id: str, 
        filename: str = "factura.jpg"
    ) -> Dict[str, Any]:
        # 1. Optimización en memoria con Pillow
        opt_bytes, mime_type = cls.optimize_image(image_bytes)

        # 2. Hash SHA-256 anti-duplicados
        sha256_hash = cls.compute_sha256(opt_bytes)
        duplicada = supabase_service.check_factura_duplicate(sha256_hash)
        if duplicada:
            return {
                "status": "error_duplicate",
                "alerta_roja": True,
                "alerta_duplicada": True,
                "alerta_sobreprecio": False,
                "alerta_fuera_partida": False,
                "detalle_alerta": f"ALERTA ROJA: Factura DUPLICADA rechazada. Ya fue registrada el {duplicada.get('fecha')} por {duplicada.get('proveedor')} (${duplicada.get('total_usd')}).",
                "factura_existente": duplicada
            }

        # 3. Extracción de ítems con Gemini Flash
        extracted = gemini_service.parse_hardware_invoice(opt_bytes, mime_type=mime_type)
        if extracted.get("error") or (float(extracted.get("total_usd", 0.0)) <= 0 and len(extracted.get("items", [])) == 0):
            return {
                "status": "error_unreadable",
                "alerta_roja": True,
                "alerta_duplicada": False,
                "alerta_sobreprecio": False,
                "alerta_fuera_partida": False,
                "detalle_alerta": extracted.get("error", "No se pudieron identificar los datos fiscales ni montos de la factura en la imagen."),
                "factura": None
            }

        total_usd = float(extracted.get("total_usd", 0.0))
        total_bs = float(extracted.get("total_bs", 0.0))
        proveedor = extracted.get("proveedor", "Ferretería General")
        nro_control = extracted.get("nro_control", "N/A")
        items = extracted.get("items", [])

        # 4. Auditoría contra Presupuesto y Hoja de Compras de la obra activa
        obra = supabase_service.get_obra(obra_id) or {}
        tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
        if total_bs <= 0 and total_usd > 0:
            total_bs = round(total_usd * tasa_bcv, 2)
        elif total_usd <= 0 and total_bs > 0:
            total_usd = round(total_bs / tasa_bcv, 2)

        hoja_compras = supabase_service.get_hoja_compras(obra_id)
        materiales_planificados = {h["material"].lower(): h for h in hoja_compras}

        alerta_sobreprecio = False
        alerta_fuera_partida = False
        mensajes_alerta = []

        # Analizar cada ítem de la factura
        for it in items:
            desc = it.get("descripcion", "").lower()
            p_unit = float(it.get("precio_unitario_usd", 0.0))
            
            # Buscar coincidencia en la hoja de compras
            coincidencia = None
            for mat_name, mat_data in materiales_planificados.items():
                # Coincidencia difusa de palabras clave
                words = [w for w in mat_name.split() if len(w) > 3]
                if any(w in desc for w in words):
                    coincidencia = mat_data
                    break

            if not coincidencia:
                # Comprobar también en catálogo base
                base_match = None
                for k, v in PRECIOS_MATERIALES_BASE.items():
                    if any(w in desc for w in v["nombre"].lower().split() if len(w) > 3):
                        base_match = v
                        break
                
                if not base_match and p_unit > 15.0:
                    alerta_fuera_partida = True
                    mensajes_alerta.append(f"Ítem fuera de presupuesto: '{it.get('descripcion')}' (${p_unit:.2f})")
            else:
                p_estimado = float(coincidencia.get("p_unit_estimado_usd", 0.0))
                if p_estimado > 0 and p_unit > (p_estimado * 1.15):  # Sobreprecio mayor al 15%
                    alerta_sobreprecio = True
                    exceso = ((p_unit - p_estimado) / p_estimado) * 100.0
                    mensajes_alerta.append(f"Sobreprecio de {exceso:.1f}% en '{it.get('descripcion')}': Cobrado ${p_unit:.2f} vs Estimado ${p_estimado:.2f}")

        # 5. Subida de imagen a Supabase Storage
        foto_url = supabase_service.upload_file(opt_bytes, filename=filename, content_type=mime_type)

        # 6. Cálculo de deducción presupuestaria y margen restante
        presupuesto_total_usd = float(obra.get("presupuesto_total_usd", 0.0))
        total_gastado_previo = float(obra.get("total_gastado_usd", 0.0))
        nuevo_gastado_total = total_gastado_previo + total_usd

        # Margen restante estimado
        if presupuesto_total_usd > 0:
            margen_restante_usd = max(0.0, presupuesto_total_usd - nuevo_gastado_total)
            margen_restante_pct = round((margen_restante_usd / presupuesto_total_usd) * 100.0, 1)
        else:
            margen_restante_usd = 0.0
            margen_restante_pct = 0.0

        alerta_roja = alerta_sobreprecio or alerta_fuera_partida
        detalle_alerta = " | ".join(mensajes_alerta) if mensajes_alerta else "Factura conforme a partidas y precios de lista."

        factura_data = {
            "obra_id": obra_id,
            "proveedor": proveedor,
            "nro_control": nro_control,
            "fecha": extracted.get("fecha", "2026-11-21"),
            "total_usd": total_usd,
            "total_bs": total_bs,
            "hash_sha256": sha256_hash,
            "foto_url": foto_url,
            "alerta_sobreprecio": alerta_sobreprecio,
            "alerta_fuera_partida": alerta_fuera_partida,
            "alerta_duplicada": False,
            "detalle_alerta": detalle_alerta,
            "items": items,
            "user_id": obra.get("user_id")
        }

        saved_factura = supabase_service.save_factura(factura_data)

        return {
            "status": "success",
            "factura": saved_factura,
            "alerta_roja": alerta_roja,
            "alerta_sobreprecio": alerta_sobreprecio,
            "alerta_fuera_partida": alerta_fuera_partida,
            "alerta_duplicada": False,
            "detalle_alerta": detalle_alerta,
            "nuevo_gastado_usd": nuevo_gastado_total,
            "margen_restante_usd": margen_restante_usd,
            "margen_restante_pct": margen_restante_pct
        }

invoice_service = InvoiceService()
