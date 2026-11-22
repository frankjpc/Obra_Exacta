import os
import uuid
import datetime
from typing import Dict, Any, List, Optional
from config import settings

def to_uuid(val: Any) -> str:
    """
    Garantiza que cualquier identificador sea un UUID válido según la sintaxis de PostgreSQL.
    Si recibe un string no-UUID (como 'demo-torre-polar-001' o 'part-01'), genera
    un UUID v5 determinista válido para evitar el error de PostgreSQL 22P02.
    """
    if not val:
        return str(uuid.uuid4())
    s = str(val).strip()
    try:
        return str(uuid.UUID(s))
    except Exception:
        # Genera un UUID v5 válido y reproducible a partir del texto
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, s))

class SupabaseService:
    """
    Servicio de Supabase con fallback local en memoria para PostgreSQL y Storage.
    Garantiza funcionamiento total tanto con credenciales de Supabase en vivo
    como en modo autónomo / demo offline sin conexión.
    """
    def __init__(self):
        self.client = None
        self.is_connected = False
        
        # Almacén en memoria para estado y fallback offline
        self._memory_store = {
            "obras": {},
            "partidas": {},
            "hoja_compras": {},
            "cargas_fiscales": {},
            "facturas": {},
            "evidencias_avance": {},
            "libro_obra": {},
            "catalogo_precios_usuario": {},
            "historial_ediciones": []
        }

        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                from supabase import create_client, Client
                self.client: Optional[Client] = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                self.is_connected = True
                print("Conectado exitosamente a Supabase.")
            except Exception as e:
                print(f"Aviso: No se pudo conectar a Supabase ({e}). Usando almacén local reactivo.")
                self.is_connected = False
        else:
            print("Supabase no configurado en .env. Usando almacén local reactivo.")

    # --------------------------------------------------------------------------
    # OBRAS
    # --------------------------------------------------------------------------
    def get_obras(self) -> List[Dict[str, Any]]:
        if self.is_connected and self.client:
            try:
                res = self.client.table("obras").select("*").order("created_at", desc=True).execute()
                return res.data or []
            except Exception as e:
                print(f"Error Supabase get_obras: {e}")
        return list(self._memory_store["obras"].values())

    def get_obra(self, obra_id: str) -> Optional[Dict[str, Any]]:
        clean_id = to_uuid(obra_id)
        if self.is_connected and self.client:
            try:
                res = self.client.table("obras").select("*").eq("id", clean_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"Error Supabase get_obra: {e}")
        return self._memory_store["obras"].get(clean_id) or self._memory_store["obras"].get(obra_id)

    def get_or_create_active_obra(self, chat_id: Optional[int] = None) -> Dict[str, Any]:
        """Obtiene la obra activa del chat o la más reciente, o crea una por defecto limpia."""
        obras = self.get_obras()
        if chat_id:
            for o in obras:
                if o.get("telegram_chat_id") == chat_id and o.get("estado") == "activa":
                    return o
        if obras:
            return obras[0]

        # Obtener tasa BCV oficial en tiempo real
        tasa = settings.TASA_BCV_DEFAULT
        try:
            from services.bcv_service import bcv_service
            bcv_info = bcv_service.get_tasa_oficial()
            tasa = bcv_info.get("tasa_bcv", settings.TASA_BCV_DEFAULT)
        except Exception:
            pass

        # Crear obra limpia por defecto con UUID válido y sin partidas precargadas
        return self.create_obra({
            "nombre": "Proyecto Principal",
            "cliente": "Cliente Principal",
            "direccion": "Sede de Obra",
            "tasa_bcv": tasa,
            "margen_meta": settings.MARGEN_META_DEFAULT,
            "presupuesto_total_usd": 0.0,
            "presupuesto_total_bs": 0.0,
            "total_gastado_usd": 0.0,
            "total_gastado_bs": 0.0,
            "estado": "activa",
            "telegram_chat_id": chat_id
        })

    def create_obra(self, data: Dict[str, Any]) -> Dict[str, Any]:
        obra_id = to_uuid(data.get("id"))
        item = {
            "id": obra_id,
            "nombre": data.get("nombre", "Nueva Obra"),
            "cliente": data.get("cliente", "Cliente General"),
            "direccion": data.get("direccion", ""),
            "tasa_bcv": float(data.get("tasa_bcv", settings.TASA_BCV_DEFAULT)),
            "margen_meta": float(data.get("margen_meta", settings.MARGEN_META_DEFAULT)),
            "presupuesto_total_usd": float(data.get("presupuesto_total_usd", 0.0)),
            "presupuesto_total_bs": float(data.get("presupuesto_total_bs", 0.0)),
            "total_gastado_usd": float(data.get("total_gastado_usd", 0.0)),
            "total_gastado_bs": float(data.get("total_gastado_bs", 0.0)),
            "estado": data.get("estado", "activa"),
            "telegram_chat_id": data.get("telegram_chat_id"),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._memory_store["obras"][obra_id] = item
        if self.is_connected and self.client:
            try:
                self.client.table("obras").upsert(item).execute()
            except Exception as e:
                print(f"Error Supabase create_obra: {e}")
        return item

    def update_obra(self, obra_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        clean_id = to_uuid(obra_id)
        obra = self.get_obra(clean_id)
        if not obra:
            return None
        obra.update(data)
        obra["id"] = clean_id
        obra["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._memory_store["obras"][clean_id] = obra
        if self.is_connected and self.client:
            try:
                self.client.table("obras").update(obra).eq("id", clean_id).execute()
            except Exception as e:
                print(f"Error Supabase update_obra: {e}")
        return obra

    # --------------------------------------------------------------------------
    # PARTIDAS
    # --------------------------------------------------------------------------
    def get_partidas(self, obra_id: str) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        partidas_list = []
        if self.is_connected and self.client:
            try:
                res = self.client.table("partidas").select("*").eq("obra_id", clean_obra_id).execute()
                partidas_list = res.data or []
            except Exception as e:
                print(f"Error Supabase get_partidas: {e}")
        if not partidas_list:
            partidas_list = [p for p in self._memory_store["partidas"].values() if p.get("obra_id") in (clean_obra_id, obra_id)]

        # Asegurar que todas las partidas expongan siempre su código COVENIN oficial
        from services.calculator import CATALOGO_COVENIN
        for p in partidas_list:
            if not p.get("codigo_covenin"):
                cov = CATALOGO_COVENIN.get(p.get("tipo_partida"), CATALOGO_COVENIN["otro"])
                p["codigo_covenin"] = cov["codigo"]
        return partidas_list

    def save_partida(self, data: Dict[str, Any]) -> Dict[str, Any]:
        p_id = to_uuid(data.get("id"))
        data["id"] = p_id
        if data.get("obra_id"):
            data["obra_id"] = to_uuid(data.get("obra_id"))
        if "created_at" not in data:
            data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        from services.calculator import CATALOGO_COVENIN
        if not data.get("codigo_covenin"):
            cov = CATALOGO_COVENIN.get(data.get("tipo_partida"), CATALOGO_COVENIN["otro"])
            data["codigo_covenin"] = cov["codigo"]

        self._memory_store["partidas"][p_id] = data

        if self.is_connected and self.client:
            allowed_cols = {
                "id", "obra_id", "tipo_partida", "descripcion", "largo", "alto", 
                "cantidad", "area", "unidad", "p_unit_usd", "total_usd", 
                "p_unit_bs", "total_bs", "porcentaje_avance", "created_at", "updated_at",
                "codigo_covenin"
            }
            db_data = {k: v for k, v in data.items() if k in allowed_cols}
            try:
                self.client.table("partidas").upsert(db_data).execute()
            except Exception as e:
                err_str = str(e)
                # Si la columna codigo_covenin aún no existe en Supabase, reintentar sin ella
                if "codigo_covenin" in err_str:
                    db_data.pop("codigo_covenin", None)
                    try:
                        self.client.table("partidas").upsert(db_data).execute()
                    except Exception as e2:
                        print(f"Error Supabase save_partida (sin covenin): {e2}")
                else:
                    print(f"Error Supabase save_partida: {e}")
        return data

    def update_partida(self, partida_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        clean_p_id = to_uuid(partida_id)
        updates["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if clean_p_id in self._memory_store["partidas"]:
            self._memory_store["partidas"][clean_p_id].update(updates)
            
        if self.is_connected and self.client:
            try:
                allowed_cols = {
                    "tipo_partida", "descripcion", "largo", "alto", 
                    "cantidad", "area", "unidad", "p_unit_usd", "total_usd", 
                    "p_unit_bs", "total_bs", "porcentaje_avance", "updated_at"
                }
                db_data = {k: v for k, v in updates.items() if k in allowed_cols}
                res = self.client.table("partidas").update(db_data).eq("id", clean_p_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"Error Supabase update_partida: {e}")
        return self._memory_store["partidas"].get(clean_p_id)

    def update_partida_avance(self, partida_id: str, porcentaje: float) -> Optional[Dict[str, Any]]:
        clean_p_id = to_uuid(partida_id)
        partida = None
        if self.is_connected and self.client:
            try:
                res = self.client.table("partidas").select("*").eq("id", clean_p_id).execute()
                if res.data:
                    partida = res.data[0]
            except Exception as e:
                print(f"Error Supabase fetch partida: {e}")
        
        if not partida:
            partida = self._memory_store["partidas"].get(clean_p_id) or self._memory_store["partidas"].get(partida_id)
            
        if partida:
            partida["porcentaje_avance"] = min(100.0, max(0.0, float(porcentaje)))
            partida["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._memory_store["partidas"][clean_p_id] = partida
            if self.is_connected and self.client:
                try:
                    self.client.table("partidas").update({
                        "porcentaje_avance": partida["porcentaje_avance"],
                        "updated_at": partida["updated_at"]
                    }).eq("id", clean_p_id).execute()
                except Exception as e:
                    print(f"Error Supabase update_partida_avance: {e}")
        return partida

    # --------------------------------------------------------------------------
    # HOJA DE COMPRAS
    # --------------------------------------------------------------------------
    def get_hoja_compras(self, obra_id: str) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        if self.is_connected and self.client:
            try:
                res = self.client.table("hoja_compras").select("*").eq("obra_id", clean_obra_id).execute()
                return res.data or []
            except Exception as e:
                print(f"Error Supabase get_hoja_compras: {e}")
        return [h for h in self._memory_store["hoja_compras"].values() if h.get("obra_id") in (clean_obra_id, obra_id)]

    def save_hoja_compras(self, obra_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        saved = []
        for item in items:
            h_id = to_uuid(item.get("id"))
            item["id"] = h_id
            item["obra_id"] = clean_obra_id
            item["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._memory_store["hoja_compras"][h_id] = item
            saved.append(item)
            if self.is_connected and self.client:
                try:
                    self.client.table("hoja_compras").upsert(item).execute()
                except Exception as e:
                    print(f"Error Supabase save_hoja_compras item: {e}")
        return saved

    # --------------------------------------------------------------------------
    # FACTURAS Y GASTOS (CON CONTROL DE DUPLICADOS SHA-256)
    # --------------------------------------------------------------------------
    def get_facturas(self, obra_id: str) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        if self.is_connected and self.client:
            try:
                res = self.client.table("facturas").select("*").eq("obra_id", clean_obra_id).order("created_at", desc=True).execute()
                return res.data or []
            except Exception as e:
                print(f"Error Supabase get_facturas: {e}")
        return [f for f in self._memory_store["facturas"].values() if f.get("obra_id") in (clean_obra_id, obra_id)]

    def check_factura_duplicate(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        if not sha256_hash:
            return None
        if self.is_connected and self.client:
            try:
                res = self.client.table("facturas").select("*").eq("hash_sha256", sha256_hash).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"Error Supabase check_duplicate: {e}")
        for f in self._memory_store["facturas"].values():
            if f.get("hash_sha256") == sha256_hash:
                return f
        return None

    def save_factura(self, data: Dict[str, Any]) -> Dict[str, Any]:
        f_id = to_uuid(data.get("id"))
        data["id"] = f_id
        if data.get("obra_id"):
            data["obra_id"] = to_uuid(data.get("obra_id"))
        if "created_at" not in data:
            data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._memory_store["facturas"][f_id] = data

        # Actualizar total gastado en la obra
        obra_id = data.get("obra_id")
        if obra_id:
            obra = self.get_obra(obra_id)
            if obra:
                t_usd = float(obra.get("total_gastado_usd", 0.0)) + float(data.get("total_usd", 0.0))
                t_bs = float(obra.get("total_gastado_bs", 0.0)) + float(data.get("total_bs", 0.0))
                self.update_obra(obra_id, {
                    "total_gastado_usd": round(t_usd, 2),
                    "total_gastado_bs": round(t_bs, 2)
                })

        if self.is_connected and self.client:
            try:
                self.client.table("facturas").upsert(data).execute()
            except Exception as e:
                print(f"Error Supabase save_factura: {e}")
        return data

    # --------------------------------------------------------------------------
    # EVIDENCIAS DE AVANCE
    # --------------------------------------------------------------------------
    def get_evidencias(self, obra_id: str) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        if self.is_connected and self.client:
            try:
                res = self.client.table("evidencias_avance").select("*").eq("obra_id", clean_obra_id).order("created_at", desc=True).execute()
                return res.data or []
            except Exception as e:
                print(f"Error Supabase get_evidencias: {e}")
        return [e for e in self._memory_store["evidencias_avance"].values() if e.get("obra_id") in (clean_obra_id, obra_id)]

    def save_evidencia(self, data: Dict[str, Any]) -> Dict[str, Any]:
        e_id = to_uuid(data.get("id"))
        data["id"] = e_id
        if data.get("obra_id"):
            data["obra_id"] = to_uuid(data.get("obra_id"))
        if data.get("partida_id"):
            data["partida_id"] = to_uuid(data.get("partida_id"))
        data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._memory_store["evidencias_avance"][e_id] = data

        if self.is_connected and self.client:
            try:
                self.client.table("evidencias_avance").upsert(data).execute()
            except Exception as e:
                print(f"Error Supabase save_evidencia: {e}")
        return data

    # --------------------------------------------------------------------------
    # LIBRO DE OBRA Y ADICIONALES (PARADAS / DAÑOS OCULTOS)
    # --------------------------------------------------------------------------
    def get_libro_obra(self, obra_id: str) -> List[Dict[str, Any]]:
        clean_obra_id = to_uuid(obra_id)
        if self.is_connected and self.client:
            try:
                res = self.client.table("libro_obra").select("*").eq("obra_id", clean_obra_id).order("created_at", desc=True).execute()
                return res.data or []
            except Exception as e:
                print(f"Error Supabase get_libro_obra: {e}")
        return [l for l in self._memory_store["libro_obra"].values() if l.get("obra_id") in (clean_obra_id, obra_id)]

    def get_incidencia_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if self.is_connected and self.client:
            try:
                # 1. Buscar primero por token_aprobacion
                res = self.client.table("libro_obra").select("*").eq("token_aprobacion", token).execute()
                if res.data:
                    return res.data[0]
                # 2. Si no, verificar si token es un UUID válido y buscar por id
                try:
                    uuid.UUID(token)
                    res_id = self.client.table("libro_obra").select("*").eq("id", token).execute()
                    if res_id.data:
                        return res_id.data[0]
                except Exception:
                    pass
            except Exception as e:
                print(f"Error Supabase get_incidencia_by_token: {e}")
        for l in self._memory_store["libro_obra"].values():
            if l.get("token_aprobacion") == token or l.get("id") == token:
                return l
        return None

    def save_incidencia(self, data: Dict[str, Any]) -> Dict[str, Any]:
        l_id = to_uuid(data.get("id"))
        data["id"] = l_id
        if data.get("obra_id"):
            data["obra_id"] = to_uuid(data.get("obra_id"))
        if "token_aprobacion" not in data:
            data["token_aprobacion"] = str(uuid.uuid4()).replace("-", "")[:16]
        if "estado_aprobacion" not in data:
            data["estado_aprobacion"] = "pendiente"
        if "created_at" not in data:
            data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._memory_store["libro_obra"][l_id] = data

        if self.is_connected and self.client:
            try:
                self.client.table("libro_obra").upsert(data).execute()
            except Exception as e:
                print(f"Error Supabase save_incidencia: {e}")
        return data

    def aprobar_incidencia(self, token_or_id: str, cliente_nombre: Optional[str] = None) -> Optional[Dict[str, Any]]:
        incidencia = self.get_incidencia_by_token(token_or_id)
        if not incidencia:
            return None

        incidencia["estado_aprobacion"] = "aprobado"
        incidencia["aprobado_en"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if cliente_nombre:
            incidencia["cliente_nombre"] = cliente_nombre
        incidencia["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Incrementar presupuesto base de la obra con el costo adicional
        obra_id = incidencia.get("obra_id")
        if obra_id:
            obra = self.get_obra(obra_id)
            if obra:
                n_pres_usd = float(obra.get("presupuesto_total_usd", 0.0)) + float(incidencia.get("costo_adicional_usd", 0.0))
                n_pres_bs = float(obra.get("presupuesto_total_bs", 0.0)) + float(incidencia.get("costo_adicional_bs", 0.0))
                self.update_obra(obra_id, {
                    "presupuesto_total_usd": round(n_pres_usd, 2),
                    "presupuesto_total_bs": round(n_pres_bs, 2)
                })

        self._memory_store["libro_obra"][incidencia["id"]] = incidencia

        if self.is_connected and self.client:
            try:
                self.client.table("libro_obra").update({
                    "estado_aprobacion": "aprobado",
                    "aprobado_en": incidencia["aprobado_en"],
                    "cliente_nombre": incidencia.get("cliente_nombre"),
                    "updated_at": incidencia["updated_at"]
                }).eq("id", incidencia["id"]).execute()
            except Exception as e:
                print(f"Error Supabase aprobar_incidencia: {e}")

        return incidencia

    # --------------------------------------------------------------------------
    # STORAGE DE ARCHIVOS (SUPABASE STORAGE / FALLBACK LOCAL)
    # --------------------------------------------------------------------------
    def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        safe_filename = f"{uuid.uuid4().hex[:12]}_{filename.replace(' ', '_')}"
        if self.is_connected and self.client:
            try:
                self.client.storage.from_(settings.SUPABASE_BUCKET).upload(
                    path=safe_filename,
                    file=file_bytes,
                    file_options={"content-type": content_type}
                )
                url = self.client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(safe_filename)
                return url
            except Exception as e:
                print(f"Error Supabase storage upload: {e}")

        os.makedirs("uploads", exist_ok=True)
        local_path = os.path.join("uploads", safe_filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return f"/api/uploads/{safe_filename}"

    # --------------------------------------------------------------------------
    # MEMORIA OPERATIVA: CATÁLOGO DE PRECIOS DEL USUARIO & HISTORIAL DE EDICIONES
    # --------------------------------------------------------------------------
    def get_catalogo_precios(self) -> List[Dict[str, Any]]:
        """Devuelve todos los precios personalizados aprendidos del contratista."""
        if self.is_connected and self.client:
            try:
                res = self.client.table("catalogo_precios_usuario").select("*").order("updated_at", desc=True).execute()
                if res.data:
                    return res.data
            except Exception:
                pass
        return list(self._memory_store["catalogo_precios_usuario"].values())

    def get_catalogo_precios_dict(self) -> Dict[str, float]:
        """Devuelve diccionario clave -> precio_usd para el calculador determinista."""
        items = self.get_catalogo_precios()
        return {item["clave_o_codigo"]: float(item["precio_usd"]) for item in items if "clave_o_codigo" in item and "precio_usd" in item}

    def save_catalogo_precio(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra o actualiza un precio personalizado en la memoria operativa."""
        clave = str(data.get("clave_o_codigo", "")).strip().lower()
        if not clave:
            clave = str(uuid.uuid4())
        
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            "id": to_uuid(data.get("id") or clave),
            "clave_o_codigo": clave,
            "nombre": data.get("nombre", clave),
            "tipo": data.get("tipo", "material"),
            "unidad": data.get("unidad", "und"),
            "precio_usd": float(data.get("precio_usd", 0.0)),
            "proveedor_opcional": data.get("proveedor_opcional"),
            "created_at": data.get("created_at") or now_iso,
            "updated_at": now_iso
        }
        self._memory_store["catalogo_precios_usuario"][clave] = item

        if self.is_connected and self.client:
            try:
                self.client.table("catalogo_precios_usuario").upsert(item).execute()
            except Exception:
                pass
        return item

    def get_historial_ediciones(self, obra_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera el historial de ediciones conversacionales solicitadas por el usuario."""
        if self.is_connected and self.client:
            try:
                q = self.client.table("historial_ediciones").select("*").order("created_at", desc=True)
                if obra_id:
                    q = q.eq("obra_id", to_uuid(obra_id))
                res = q.execute()
                if res.data:
                    return res.data
            except Exception:
                pass
        
        if obra_id:
            clean_id = to_uuid(obra_id)
            return [h for h in self._memory_store["historial_ediciones"] if h.get("obra_id") in (clean_id, obra_id)]
        return list(reversed(self._memory_store["historial_ediciones"]))

    def save_edicion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra una modificación en el historial de ediciones."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        item = {
            "id": to_uuid(data.get("id")),
            "obra_id": to_uuid(data.get("obra_id")),
            "accion": data.get("accion", "modificar_precio"),
            "partida_o_material": data.get("partida_o_material", ""),
            "valor_anterior": str(data.get("valor_anterior", "")),
            "valor_nuevo": str(data.get("valor_nuevo", "")),
            "detalles": data.get("detalles", {}),
            "created_at": now_iso
        }
        self._memory_store["historial_ediciones"].append(item)

        if self.is_connected and self.client:
            try:
                self.client.table("historial_ediciones").insert(item).execute()
            except Exception:
                pass
        return item

    # --------------------------------------------------------------------------
    # SEED DEMO DATA CON UUIDs VÁLIDOS
    # --------------------------------------------------------------------------
    def seed_demo_data(self) -> Dict[str, Any]:
        """Carga una obra completa con partidas, compras, gastos, avance e incidencias con UUIDs válidos."""
        obra_id = "00000000-0000-4000-8000-000000000001"
        obra_data = {
            "id": obra_id,
            "nombre": "Remodelación Oficinas Torre Polar - Piso 8",
            "cliente": "Inversiones Capital 360 C.A.",
            "direccion": "Av. Francisco de Miranda, Los Palos Grandes, Caracas",
            "tasa_bcv": settings.TASA_BCV_DEFAULT,
            "margen_meta": 32.0,
            "presupuesto_total_usd": 4850.00,
            "presupuesto_total_bs": 332225.00,
            "total_gastado_usd": 1420.00,
            "total_gastado_bs": 97270.00,
            "estado": "activa"
        }
        self.create_obra(obra_data)

        # Partidas tabuladas 2D con UUIDs válidos
        partidas_demo = [
            {
                "id": "00000000-0000-4000-8000-000000000011",
                "obra_id": obra_id,
                "tipo_partida": "pared_bloque",
                "descripcion": "Tabiquería de bloque de cemento 15cm frisado a dos caras",
                "largo": 12.0,
                "alto": 2.8,
                "cantidad": 1.0,
                "area": 33.6,
                "unidad": "m2",
                "p_unit_usd": 24.50,
                "total_usd": 823.20,
                "p_unit_bs": 1678.25,
                "total_bs": 56389.20,
                "porcentaje_avance": 85.0
            },
            {
                "id": "00000000-0000-4000-8000-000000000012",
                "obra_id": obra_id,
                "tipo_partida": "cielo_raso",
                "descripcion": "Cielo raso suspendido en placas de yeso 1/2 pulgada con perfilería oculta",
                "largo": 8.5,
                "alto": 6.0,
                "cantidad": 1.0,
                "area": 51.0,
                "unidad": "m2",
                "p_unit_usd": 21.00,
                "total_usd": 1071.00,
                "p_unit_bs": 1438.50,
                "total_bs": 73363.50,
                "porcentaje_avance": 60.0
            },
            {
                "id": "00000000-0000-4000-8000-000000000013",
                "obra_id": obra_id,
                "tipo_partida": "ceramica",
                "descripcion": "Revestimiento de piso con porcelanato pulido 60x60 alto tráfico",
                "largo": 8.5,
                "alto": 6.0,
                "cantidad": 1.0,
                "area": 51.0,
                "unidad": "m2",
                "p_unit_usd": 28.50,
                "total_usd": 1453.50,
                "p_unit_bs": 1952.25,
                "total_bs": 99564.75,
                "porcentaje_avance": 40.0
            },
            {
                "id": "00000000-0000-4000-8000-000000000014",
                "obra_id": obra_id,
                "tipo_partida": "pintura",
                "descripcion": "Pintura satinada blanco ostra tipo A en paredes internas a dos manos",
                "largo": 25.0,
                "alto": 2.8,
                "cantidad": 1.0,
                "area": 70.0,
                "unidad": "m2",
                "p_unit_usd": 7.80,
                "total_usd": 546.00,
                "p_unit_bs": 534.30,
                "total_bs": 37401.00,
                "porcentaje_avance": 20.0
            },
            {
                "id": "00000000-0000-4000-8000-000000000015",
                "obra_id": obra_id,
                "tipo_partida": "lampara",
                "descripcion": "Suministro e instalación de luminarias LED 60x60 de 48W con difusor",
                "largo": 0.0,
                "alto": 0.0,
                "cantidad": 18.0,
                "area": 18.0,
                "unidad": "piezas",
                "p_unit_usd": 23.00,
                "total_usd": 414.00,
                "p_unit_bs": 1575.50,
                "total_bs": 28359.00,
                "porcentaje_avance": 0.0
            }
        ]
        for p in partidas_demo:
            self.save_partida(p)

        # Hoja de compras consolidada demo con UUIDs válidos
        hoja_demo = [
            {"id": "00000000-0000-4000-8000-000000000031", "obra_id": obra_id, "material": "Bloque de cemento/arcilla 15cm", "unidad": "piezas", "cantidad_requerida": 470, "cantidad_comprada": 470, "p_unit_estimado_usd": 0.65, "total_estimado_usd": 305.50, "total_comprado_usd": 305.50},
            {"id": "00000000-0000-4000-8000-000000000032", "obra_id": obra_id, "material": "Cemento gris Portland (42.5kg)", "unidad": "sacos", "cantidad_requerida": 25, "cantidad_comprada": 20, "p_unit_estimado_usd": 8.50, "total_estimado_usd": 212.50, "total_comprado_usd": 170.00},
            {"id": "00000000-0000-4000-8000-000000000033", "obra_id": obra_id, "material": "Arena lavada de río", "unidad": "m3", "cantidad_requerida": 3.0, "cantidad_comprada": 3.0, "p_unit_estimado_usd": 28.00, "total_estimado_usd": 84.00, "total_comprado_usd": 84.00},
            {"id": "00000000-0000-4000-8000-000000000034", "obra_id": obra_id, "material": "Pego gris para cerámica (14kg)", "unidad": "sacos", "cantidad_requerida": 13, "cantidad_comprada": 10, "p_unit_estimado_usd": 6.00, "total_estimado_usd": 78.00, "total_comprado_usd": 60.00},
            {"id": "00000000-0000-4000-8000-000000000035", "obra_id": obra_id, "material": "Láminas de yeso 1/2 pulg", "unidad": "m2", "cantidad_requerida": 54, "cantidad_comprada": 40, "p_unit_estimado_usd": 9.50, "total_estimado_usd": 513.00, "total_comprado_usd": 380.00},
            {"id": "00000000-0000-4000-8000-000000000036", "obra_id": obra_id, "material": "Pintura satinada blanco ostra", "unidad": "galones", "cantidad_requerida": 4, "cantidad_comprada": 2, "p_unit_estimado_usd": 32.00, "total_estimado_usd": 128.00, "total_comprado_usd": 64.00},
            {"id": "00000000-0000-4000-8000-000000000037", "obra_id": obra_id, "material": "Luminarias LED 60x60 48W", "unidad": "piezas", "cantidad_requerida": 18, "cantidad_comprada": 0, "p_unit_estimado_usd": 16.00, "total_estimado_usd": 288.00, "total_comprado_usd": 0.00}
        ]
        self.save_hoja_compras(obra_id, hoja_demo)

        # Facturas de ferretería demo con alerta de sobreprecio
        factura_1 = {
            "id": "00000000-0000-4000-8000-000000000041",
            "obra_id": obra_id,
            "proveedor": "Ferretería Epa San Martín",
            "nro_control": "FAC-008921",
            "fecha": "2026-11-18",
            "total_usd": 620.00,
            "total_bs": 42470.00,
            "hash_sha256": "f4b3c8e1920aa94101e998a44b3c0e1188339aa55bcde190a4422eacb1234567",
            "foto_url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=600&q=80",
            "alerta_sobreprecio": False,
            "alerta_fuera_partida": False,
            "alerta_duplicada": False,
            "detalle_alerta": "Factura dentro de partidas y precios acordados.",
            "items": [
                {"descripcion": "Bloque cemento 15cm (470 uds)", "cantidad": 470, "precio_unitario_usd": 0.65, "total_usd": 305.50},
                {"descripcion": "Cemento gris Portland (20 sacos)", "cantidad": 20, "precio_unitario_usd": 8.50, "total_usd": 170.00},
                {"descripcion": "Pego gris 14kg (10 sacos)", "cantidad": 10, "precio_unitario_usd": 6.00, "total_usd": 60.00},
                {"descripcion": "Arena lavada (3 m3)", "cantidad": 3, "precio_unitario_usd": 28.00, "total_usd": 84.00}
            ]
        }
        factura_2 = {
            "id": "00000000-0000-4000-8000-000000000042",
            "obra_id": obra_id,
            "proveedor": "Materiales Delicias C.A.",
            "nro_control": "FAC-009412",
            "fecha": "2026-11-20",
            "total_usd": 800.00,
            "total_bs": 54800.00,
            "hash_sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
            "foto_url": "https://images.unsplash.com/photo-1554415707-9e44667ff4f0?auto=format&fit=crop&w=600&q=80",
            "alerta_sobreprecio": True,
            "alerta_fuera_partida": True,
            "alerta_duplicada": False,
            "detalle_alerta": "ALERTA ROJA: Sobreprecio en Láminas de yeso ($12.00 vs $9.50 presupuestado) e ítem fuera de partida detectado (Brocas de tungsteno $40.00).",
            "items": [
                {"descripcion": "Láminas de yeso 1/2 pulgada (40 m2)", "cantidad": 40, "precio_unitario_usd": 12.00, "total_usd": 480.00},
                {"descripcion": "Pintura satinada blanco ostra (2 gal)", "cantidad": 2, "precio_unitario_usd": 32.00, "total_usd": 64.00},
                {"descripcion": "Brocas de tungsteno para concreto (2 kits)", "cantidad": 2, "precio_unitario_usd": 20.00, "total_usd": 40.00},
                {"descripcion": "Flete y acarreo no presupuestado", "cantidad": 1, "precio_unitario_usd": 216.00, "total_usd": 216.00}
            ]
        }
        self.save_factura(factura_1)
        self.save_factura(factura_2)

        # Incidencia de Daño Oculto demo con UUID válido
        incidencia_demo = {
            "id": "00000000-0000-4000-8000-000000000051",
            "obra_id": obra_id,
            "tipo": "parada_dano_oculto",
            "titulo": "Fuga en tubería matriz de aguas servidas oculta en pared este",
            "descripcion": "Al demoler el friso viejo se halló tubería de hierro fundido de 4 pulgadas fracturada con filtración activa. Se paralizó el vaciado de piso para evitar daño estructural.",
            "foto_url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=800&q=80",
            "costo_adicional_usd": 380.00,
            "costo_adicional_bs": 26030.00,
            "porcentaje_variacion": 7.84,  # (380 / 4850) * 100
            "token_aprobacion": "demo-token-aprobacion-001",
            "estado_aprobacion": "pendiente",
            "cliente_nombre": "Inversiones Capital 360 C.A."
        }
        self.save_incidencia(incidencia_demo)

        return {"status": "ok", "obra_id": obra_id, "message": "Datos de obra demo cargados exitosamente con UUIDs válidos."}

    def clear_all_data(self, create_default: bool = True) -> Dict[str, Any]:
        """
        Limpia completamente todas las tablas de Supabase y el almacén en memoria
        (libro_obra, evidencias_avance, facturas, hoja_compras, cargas_fiscales, partidas, obras).
        Opcionalmente crea una obra limpia inicial con presupuesto y gastos en 0.
        """
        deleted_counts = {}
        tables_to_clear = [
            "historial_ediciones",
            "libro_obra",
            "evidencias_avance",
            "facturas",
            "hoja_compras",
            "cargas_fiscales",
            "partidas",
            "obras"
        ]

        if self.is_connected and self.client:
            for tbl in tables_to_clear:
                try:
                    res = self.client.table(tbl).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                    deleted_counts[tbl] = len(res.data) if res.data else 0
                except Exception as e:
                    print(f"Error limpiando tabla {tbl} en Supabase: {e}")
                    deleted_counts[tbl] = f"error: {e}"

        # Limpiar almacén en memoria
        for k in self._memory_store:
            self._memory_store[k] = {}

        obra_limpia = None
        if create_default:
            obra_limpia = self.get_or_create_active_obra()

        return {
            "status": "success",
            "message": "Base de datos limpiada exitosamente.",
            "deleted_counts": deleted_counts,
            "obra_activa": obra_limpia
        }

supabase_service = SupabaseService()
