from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# ==============================================================================
# TABLAS DETERMINISTAS DE RENDIMIENTOS Y PRECIOS BASE (EDITABLES)
# ==============================================================================

PRECIOS_MATERIALES_BASE = {
    "bloque_15cm": {"nombre": "Bloque de cemento/arcilla 15cm", "unidad": "piezas", "p_unit_usd": 0.65},
    "arena_lavada": {"nombre": "Arena lavada de río", "unidad": "m3", "p_unit_usd": 28.00},
    "cemento_gris": {"nombre": "Cemento gris Portland (42.5kg)", "unidad": "sacos", "p_unit_usd": 8.50},
    "pintura_caucho": {"nombre": "Pintura de caucho profesional (2 manos)", "unidad": "galones", "p_unit_usd": 32.00},
    "ceramica_piso": {"nombre": "Cerámica esmaltada de alto tráfico", "unidad": "m2", "p_unit_usd": 14.50},
    "pego_gris": {"nombre": "Pego gris para cerámica (14kg)", "unidad": "sacos", "p_unit_usd": 6.00},
    "lamina_drywall": {"nombre": "Láminas de yeso/cielo raso 1/2 pulg", "unidad": "m2", "p_unit_usd": 9.50},
    "perfileria_cielo": {"nombre": "Perfilería metálica galvanizada cielo raso", "unidad": "ml", "p_unit_usd": 4.20},
    "lampara_led": {"nombre": "Luminaria LED Panel 60x60 / Empotrable", "unidad": "piezas", "p_unit_usd": 16.00},
    "cable_conectores": {"nombre": "Cableado THW #12 y conectores", "unidad": "ml", "p_unit_usd": 1.80},
}

MANO_DE_OBRA_BASE = {
    "pared_bloque": 7.50,   # USD / m2
    "pintura": 3.20,        # USD / m2
    "ceramica": 8.00,       # USD / m2
    "cielo_raso": 6.50,     # USD / m2
    "lampara": 6.00,        # USD / pieza
    "otro": 5.00            # USD unitario
}

# ==============================================================================
# CATÁLOGO DE CÓDIGOS OFICIALES COVENIN VENEZUELA (LICITACIONES)
# ==============================================================================
CATALOGO_COVENIN = {
    "pared_bloque": {
        "codigo": "E-411.011.015",
        "descripcion": "Construcción de paredes de bloques de arcilla/concreto e=15 cm",
        "unidad": "m2"
    },
    "pintura": {
        "codigo": "E-463.100.503",
        "descripcion": "Pintura de caucho interior/exterior, dos manos",
        "unidad": "m2"
    },
    "ceramica": {
        "codigo": "E-414.031.010",
        "descripcion": "Revestimiento interior en pisos/paredes con cerámica nacional",
        "unidad": "m2"
    },
    "cielo_raso": {
        "codigo": "E-419.110.000",
        "descripcion": "Suministro e instalación de cielo raso en láminas (suspensión visible/invisible)",
        "unidad": "m2"
    },
    "lampara": {
        "codigo": "E-611.010.000",
        "descripcion": "Suministro e instalación de luminaria/lámpara tipo LED",
        "unidad": "piezas"
    },
    "otro": {
        "codigo": "E-GEN.000.001",
        "descripcion": "Partida complementaria general de obra civil",
        "unidad": "und"
    }
}

class PartidaInput(BaseModel):
    tipo_partida: str  # pared_bloque, pintura, ceramica, cielo_raso, lampara, otro
    descripcion: Optional[str] = None
    codigo_covenin: Optional[str] = None
    largo: Optional[float] = 0.0
    alto: Optional[float] = 0.0
    cantidad: Optional[float] = 1.0
    area: Optional[float] = 0.0
    unidad: Optional[str] = None
    p_unit_usd_override: Optional[float] = None

class MaterialDesglose(BaseModel):
    material_key: str
    nombre: str
    unidad: str
    cantidad: float
    p_unit_usd: float
    total_usd: float

class PartidaCalculada(BaseModel):
    codigo_covenin: str = Field(default="E-GEN.000.001")
    tipo_partida: str
    descripcion: str
    unidad: str
    cantidad: float
    area: float
    largo: float
    alto: float
    # Tabla bimonetaria de 6/7 columnas
    p_unit_usd: float
    total_usd: float
    p_unit_bs: float
    total_bs: float
    # Detalle interno
    costo_materiales_usd: float
    costo_mano_obra_usd: float
    materiales: List[MaterialDesglose] = []
    porcentaje_avance: float = 0.0

class CargaFiscal(BaseModel):
    nombre: str
    porcentaje: float
    aplica_sobre: str  # mano_de_obra, materiales, subtotal
    monto_usd: float
    monto_bs: float

class HojaComprasItem(BaseModel):
    material: str
    unidad: str
    cantidad_requerida: float
    cantidad_comprada: float = 0.0
    p_unit_estimado_usd: float
    total_estimado_usd: float
    total_comprado_usd: float = 0.0

class PresupuestoCompleto(BaseModel):
    obra_id: Optional[str] = None
    tasa_bcv: float
    partidas: List[PartidaCalculada]
    cargas_fiscales: List[CargaFiscal]
    hoja_compras: List[HojaComprasItem]
    # Totales consolidados
    subtotal_usd: float
    subtotal_bs: float
    total_cargas_usd: float
    total_cargas_bs: float
    total_general_usd: float
    total_general_bs: float
    total_mano_obra_usd: float
    total_materiales_usd: float

class ConstructionCalculator:
    """
    Motor determinista en Python:
    Gemini NUNCA calcula cantidades de materiales ni precios; solo extrae parámetros.
    Este motor aplica los rendimientos certificados de construcción venezolana/latam.
    """

    @staticmethod
    def get_material_info(key: str, precios_personalizados: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        info = PRECIOS_MATERIALES_BASE.get(key, {"nombre": key, "unidad": "und", "p_unit_usd": 10.0}).copy()
        if precios_personalizados and key in precios_personalizados:
            info["p_unit_usd"] = float(precios_personalizados[key])
        return info

    @staticmethod
    def get_mano_obra(tipo: str, precios_personalizados: Optional[Dict[str, float]] = None) -> float:
        base = MANO_DE_OBRA_BASE.get(tipo, 5.0)
        mo_key = f"mano_de_obra_{tipo}"
        if precios_personalizados and mo_key in precios_personalizados:
            return float(precios_personalizados[mo_key])
        return base

    @classmethod
    def calcular_partida(
        cls, 
        item: PartidaInput, 
        tasa_bcv: float,
        precios_personalizados: Optional[Dict[str, float]] = None
    ) -> PartidaCalculada:
        tipo = item.tipo_partida.lower().strip()
        cantidad = float(item.cantidad) if (item.cantidad and item.cantidad > 0) else 1.0
        largo = float(item.largo) if item.largo else 0.0
        alto = float(item.alto) if item.alto else 0.0
        
        # Código oficial COVENIN
        covenin_info = CATALOGO_COVENIN.get(tipo, CATALOGO_COVENIN["otro"])
        codigo_covenin = item.codigo_covenin or covenin_info["codigo"]

        # Calcular área si aplica
        if item.area and item.area > 0:
            area = float(item.area) * cantidad
        elif largo > 0 and alto > 0:
            area = (largo * alto) * cantidad
        elif largo > 0:
            area = largo * cantidad
        else:
            area = cantidad

        materiales: List[MaterialDesglose] = []
        costo_materiales = 0.0
        costo_mano_obra = 0.0
        unidad = covenin_info["unidad"]
        desc = item.descripcion or ""

        # Rendimientos exactos tabulados según requerimiento con memoria de precios
        if tipo == "pared_bloque":
            unidad = "m2"
            if not desc:
                desc = f"{covenin_info['descripcion']} ({area:.2f} m²)"
            # 14 bloques/m²
            cant_bloques = round(area * 14.0, 2)
            # 0.08 m³ arena/m²
            cant_arena = round(area * 0.08, 3)
            # 0.35 sacos cemento/m²
            cant_cemento = round(area * 0.35, 2)

            b_info = cls.get_material_info("bloque_15cm", precios_personalizados)
            a_info = cls.get_material_info("arena_lavada", precios_personalizados)
            c_info = cls.get_material_info("cemento_gris", precios_personalizados)

            materiales.append(MaterialDesglose(
                material_key="bloque_15cm",
                nombre=b_info["nombre"],
                unidad=b_info["unidad"],
                cantidad=cant_bloques,
                p_unit_usd=b_info["p_unit_usd"],
                total_usd=round(cant_bloques * b_info["p_unit_usd"], 2)
            ))
            materiales.append(MaterialDesglose(
                material_key="arena_lavada",
                nombre=a_info["nombre"],
                unidad=a_info["unidad"],
                cantidad=cant_arena,
                p_unit_usd=a_info["p_unit_usd"],
                total_usd=round(cant_arena * a_info["p_unit_usd"], 2)
            ))
            materiales.append(MaterialDesglose(
                material_key="cemento_gris",
                nombre=c_info["nombre"],
                unidad=c_info["unidad"],
                cantidad=cant_cemento,
                p_unit_usd=c_info["p_unit_usd"],
                total_usd=round(cant_cemento * c_info["p_unit_usd"], 2)
            ))

            costo_materiales = sum(m.total_usd for m in materiales)
            costo_mano_obra = round(area * cls.get_mano_obra("pared_bloque", precios_personalizados), 2)

        elif tipo == "pintura":
            unidad = "m2"
            if not desc:
                desc = f"{covenin_info['descripcion']} ({area:.2f} m²)"
            # 0.04 galones/m² (2 manos)
            cant_pintura = round(area * 0.04, 2)
            p_info = cls.get_material_info("pintura_caucho", precios_personalizados)

            materiales.append(MaterialDesglose(
                material_key="pintura_caucho",
                nombre=p_info["nombre"],
                unidad=p_info["unidad"],
                cantidad=cant_pintura,
                p_unit_usd=p_info["p_unit_usd"],
                total_usd=round(cant_pintura * p_info["p_unit_usd"], 2)
            ))

            costo_materiales = sum(m.total_usd for m in materiales)
            costo_mano_obra = round(area * cls.get_mano_obra("pintura", precios_personalizados), 2)

        elif tipo == "ceramica":
            unidad = "m2"
            if not desc:
                desc = f"{covenin_info['descripcion']} ({area:.2f} m²)"
            # 1.05 m² cerámica (5% desperdicio) + 0.25 sacos pego/m²
            cant_ceramica = round(area * 1.05, 2)
            cant_pego = round(area * 0.25, 2)

            cer_info = cls.get_material_info("ceramica_piso", precios_personalizados)
            peg_info = cls.get_material_info("pego_gris", precios_personalizados)

            materiales.append(MaterialDesglose(
                material_key="ceramica_piso",
                nombre=cer_info["nombre"],
                unidad=cer_info["unidad"],
                cantidad=cant_ceramica,
                p_unit_usd=cer_info["p_unit_usd"],
                total_usd=round(cant_ceramica * cer_info["p_unit_usd"], 2)
            ))
            materiales.append(MaterialDesglose(
                material_key="pego_gris",
                nombre=peg_info["nombre"],
                unidad=peg_info["unidad"],
                cantidad=cant_pego,
                p_unit_usd=peg_info["p_unit_usd"],
                total_usd=round(cant_pego * peg_info["p_unit_usd"], 2)
            ))

            costo_materiales = sum(m.total_usd for m in materiales)
            costo_mano_obra = round(area * cls.get_mano_obra("ceramica", precios_personalizados), 2)

        elif tipo == "cielo_raso":
            unidad = "m2"
            if not desc:
                desc = f"{covenin_info['descripcion']} ({area:.2f} m²)"
            # láminas + perfilería por m²
            cant_laminas = round(area * 1.05, 2)
            cant_perfil = round(area * 1.80, 2)

            lam_info = cls.get_material_info("lamina_drywall", precios_personalizados)
            per_info = cls.get_material_info("perfileria_cielo", precios_personalizados)

            materiales.append(MaterialDesglose(
                material_key="lamina_drywall",
                nombre=lam_info["nombre"],
                unidad=lam_info["unidad"],
                cantidad=cant_laminas,
                p_unit_usd=lam_info["p_unit_usd"],
                total_usd=round(cant_laminas * lam_info["p_unit_usd"], 2)
            ))
            materiales.append(MaterialDesglose(
                material_key="perfileria_cielo",
                nombre=per_info["nombre"],
                unidad=per_info["unidad"],
                cantidad=cant_perfil,
                p_unit_usd=per_info["p_unit_usd"],
                total_usd=round(cant_perfil * per_info["p_unit_usd"], 2)
            ))

            costo_materiales = sum(m.total_usd for m in materiales)
            costo_mano_obra = round(area * cls.get_mano_obra("cielo_raso", precios_personalizados), 2)

        elif tipo == "lampara":
            unidad = "piezas"
            if not desc:
                desc = f"{covenin_info['descripcion']} ({cantidad:.0f} piezas)"
            cant_piezas = round(cantidad, 2)
            cant_cable = round(cantidad * 2.5, 2)

            lamp_info = cls.get_material_info("lampara_led", precios_personalizados)
            cab_info = cls.get_material_info("cable_conectores", precios_personalizados)

            materiales.append(MaterialDesglose(
                material_key="lampara_led",
                nombre=lamp_info["nombre"],
                unidad=lamp_info["unidad"],
                cantidad=cant_piezas,
                p_unit_usd=lamp_info["p_unit_usd"],
                total_usd=round(cant_piezas * lamp_info["p_unit_usd"], 2)
            ))
            materiales.append(MaterialDesglose(
                material_key="cable_conectores",
                nombre=cab_info["nombre"],
                unidad=cab_info["unidad"],
                cantidad=cant_cable,
                p_unit_usd=cab_info["p_unit_usd"],
                total_usd=round(cant_cable * cab_info["p_unit_usd"], 2)
            ))

            costo_materiales = sum(m.total_usd for m in materiales)
            costo_mano_obra = round(cant_piezas * cls.get_mano_obra("lampara", precios_personalizados), 2)

        else:
            # Tipo libre u otro
            unidad = item.unidad or covenin_info["unidad"]
            if not desc:
                desc = f"{covenin_info['descripcion']} ({cantidad:.2f} {unidad})"
            costo_materiales = round(cantidad * 10.0, 2)
            costo_mano_obra = round(cantidad * cls.get_mano_obra("otro", precios_personalizados), 2)

        # Precio total y unitario
        divisor = area if unidad == "m2" and area > 0 else (cantidad if cantidad > 0 else 1.0)
        
        # Override de precio unitario si el usuario lo especificó o si está en memoria operativa
        override_p = item.p_unit_usd_override
        if not override_p and precios_personalizados:
            if codigo_covenin in precios_personalizados:
                override_p = float(precios_personalizados[codigo_covenin])
            elif f"partida_{tipo}" in precios_personalizados:
                override_p = float(precios_personalizados[f"partida_{tipo}"])
            elif tipo in precios_personalizados:
                override_p = float(precios_personalizados[tipo])

        if override_p and override_p > 0:
            p_unit_usd = round(override_p, 2)
            total_usd = round(p_unit_usd * divisor, 2)
        else:
            total_usd = round(costo_materiales + costo_mano_obra, 2)
            p_unit_usd = round(total_usd / divisor, 2) if divisor > 0 else total_usd

        # Conversión estricta a Bolívares según Tasa BCV
        total_bs = round(total_usd * tasa_bcv, 2)
        p_unit_bs = round(p_unit_usd * tasa_bcv, 2)

        return PartidaCalculada(
            codigo_covenin=codigo_covenin,
            tipo_partida=tipo,
            descripcion=desc,
            unidad=unidad,
            cantidad=cantidad,
            area=area,
            largo=largo,
            alto=alto,
            p_unit_usd=p_unit_usd,
            total_usd=total_usd,
            p_unit_bs=p_unit_bs,
            total_bs=total_bs,
            costo_materiales_usd=costo_materiales,
            costo_mano_obra_usd=costo_mano_obra,
            materiales=materiales,
            porcentaje_avance=0.0
        )

    @classmethod
    def procesar_presupuesto(
        cls, 
        partidas_raw: List[PartidaInput], 
        tasa_bcv: float = 918.77,
        cargas_personalizadas: Optional[List[Dict[str, Any]]] = None,
        precios_personalizados: Optional[Dict[str, float]] = None
    ) -> PresupuestoCompleto:
        """
        Calcula la tabla de 7 columnas (con COVENIN), consolida la Hoja de Compras Estimada
        y aplica el bloque de Cargas Fiscales / Indirectos con memoria operativa.
        """
        partidas_calc: List[PartidaCalculada] = []
        for p in partidas_raw:
            partidas_calc.append(cls.calcular_partida(p, tasa_bcv, precios_personalizados))

        subtotal_usd = round(sum(p.total_usd for p in partidas_calc), 2)
        subtotal_bs = round(sum(p.total_bs for p in partidas_calc), 2)
        total_mano_obra_usd = round(sum(p.costo_mano_obra_usd for p in partidas_calc), 2)
        total_materiales_usd = round(sum(p.costo_materiales_usd for p in partidas_calc), 2)

        # Consolidación automática de la Hoja de Compras Estimada
        materiales_dict: Dict[str, Dict[str, Any]] = {}
        for p in partidas_calc:
            for m in p.materiales:
                if m.nombre not in materiales_dict:
                    materiales_dict[m.nombre] = {
                        "material": m.nombre,
                        "unidad": m.unidad,
                        "cantidad_requerida": 0.0,
                        "p_unit_estimado_usd": m.p_unit_usd,
                        "total_estimado_usd": 0.0
                    }
                materiales_dict[m.nombre]["cantidad_requerida"] += m.cantidad
                materiales_dict[m.nombre]["total_estimado_usd"] += m.total_usd

        hoja_compras = [
            HojaComprasItem(
                material=v["material"],
                unidad=v["unidad"],
                cantidad_requerida=round(v["cantidad_requerida"], 2),
                cantidad_comprada=0.0,
                p_unit_estimado_usd=v["p_unit_estimado_usd"],
                total_estimado_usd=round(v["total_estimado_usd"], 2),
                total_comprado_usd=0.0
            )
            for v in materiales_dict.values()
        ]

        # Bloque editable de cargas fiscales e indirectos
        cargas_fiscales: List[CargaFiscal] = []
        if cargas_personalizadas is not None:
            for c in cargas_personalizadas:
                porc = float(c.get("porcentaje", 0.0))
                aplica = c.get("aplica_sobre", "mano_de_obra")
                base = total_mano_obra_usd if aplica == "mano_de_obra" else (total_materiales_usd if aplica == "materiales" else subtotal_usd)
                monto_u = round(base * (porc / 100.0), 2)
                monto_b = round(monto_u * tasa_bcv, 2)
                cargas_fiscales.append(CargaFiscal(
                    nombre=c.get("nombre", "Carga"),
                    porcentaje=porc,
                    aplica_sobre=aplica,
                    monto_usd=monto_u,
                    monto_bs=monto_b
                ))
        else:
            # Cargas por defecto: 9% Ley de Protección de Pensiones sobre mano de obra
            pension_monto_usd = round(total_mano_obra_usd * 0.09, 2)
            cargas_fiscales.append(CargaFiscal(
                nombre="Ley de Protección de Pensiones (9% s/Mano de Obra)",
                porcentaje=9.0,
                aplica_sobre="mano_de_obra",
                monto_usd=pension_monto_usd,
                monto_bs=round(pension_monto_usd * tasa_bcv, 2)
            ))
            # 10% Costos Indirectos / Administración sobre subtotal
            admin_monto_usd = round(subtotal_usd * 0.10, 2)
            cargas_fiscales.append(CargaFiscal(
                nombre="Administración y Costos Indirectos (10%)",
                porcentaje=10.0,
                aplica_sobre="subtotal",
                monto_usd=admin_monto_usd,
                monto_bs=round(admin_monto_usd * tasa_bcv, 2)
            ))

        total_cargas_usd = round(sum(c.monto_usd for c in cargas_fiscales), 2)
        total_cargas_bs = round(sum(c.monto_bs for c in cargas_fiscales), 2)

        total_general_usd = round(subtotal_usd + total_cargas_usd, 2)
        total_general_bs = round(subtotal_bs + total_cargas_bs, 2)

        return PresupuestoCompleto(
            tasa_bcv=tasa_bcv,
            partidas=partidas_calc,
            cargas_fiscales=cargas_fiscales,
            hoja_compras=hoja_compras,
            subtotal_usd=subtotal_usd,
            subtotal_bs=subtotal_bs,
            total_cargas_usd=total_cargas_usd,
            total_cargas_bs=total_cargas_bs,
            total_general_usd=total_general_usd,
            total_general_bs=total_general_bs,
            total_mano_obra_usd=total_mano_obra_usd,
            total_materiales_usd=total_materiales_usd
        )
