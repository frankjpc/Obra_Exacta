import pytest
from services.calculator import ConstructionCalculator, PartidaInput
from services.invoice_service import invoice_service

def test_pared_bloque_calculation():
    # 10m de largo x 3m de alto = 30 m2
    inp = PartidaInput(
        tipo_partida="pared_bloque",
        largo=10.0,
        alto=3.0,
        cantidad=1.0
    )
    res = ConstructionCalculator.calcular_partida(inp, tasa_bcv=70.0)
    
    assert res.area == 30.0
    assert res.unidad == "m2"
    # 14 bloques/m² * 30 m² = 420 bloques
    bloques = next(m for m in res.materiales if m.material_key == "bloque_15cm")
    assert bloques.cantidad == 420.0
    # 0.08 m³ arena/m² * 30 = 2.4 m³
    arena = next(m for m in res.materiales if m.material_key == "arena_lavada")
    assert arena.cantidad == 2.4
    # 0.35 sacos cemento/m² * 30 = 10.5 sacos
    cemento = next(m for m in res.materiales if m.material_key == "cemento_gris")
    assert cemento.cantidad == 10.5

    # Verificación bimonetaria estricta
    assert res.total_bs == round(res.total_usd * 70.0, 2)
    assert res.p_unit_bs == round(res.p_unit_usd * 70.0, 2)

def test_pintura_calculation():
    # 50 m2
    inp = PartidaInput(tipo_partida="pintura", area=50.0)
    res = ConstructionCalculator.calcular_partida(inp, tasa_bcv=68.50)
    assert res.area == 50.0
    pintura = next(m for m in res.materiales if m.material_key == "pintura_caucho")
    # 0.04 galones/m² * 50 = 2.0 galones
    assert pintura.cantidad == 2.0
    assert res.total_bs == round(res.total_usd * 68.50, 2)

def test_ceramica_calculation():
    # 20 m2
    inp = PartidaInput(tipo_partida="ceramica", area=20.0)
    res = ConstructionCalculator.calcular_partida(inp, tasa_bcv=68.50)
    # 1.05 * 20 = 21.0 m² cerámica
    cer = next(m for m in res.materiales if m.material_key == "ceramica_piso")
    assert cer.cantidad == 21.0
    # 0.25 * 20 = 5.0 sacos pego
    pego = next(m for m in res.materiales if m.material_key == "pego_gris")
    assert pego.cantidad == 5.0

def test_presupuesto_completo_con_ley_pensiones_y_consolidacion():
    partidas = [
        PartidaInput(tipo_partida="pared_bloque", largo=10.0, alto=2.5),  # 25 m2
        PartidaInput(tipo_partida="pintura", area=40.0),                  # 40 m2
        PartidaInput(tipo_partida="lampara", cantidad=10.0)               # 10 uds
    ]
    pres = ConstructionCalculator.procesar_presupuesto(partidas, tasa_bcv=68.50)
    
    # Debe existir la carga de la Ley de Pensiones (9% sobre mano de obra)
    carga_pension = next(c for c in pres.cargas_fiscales if "Pensiones" in c.nombre)
    assert carga_pension.porcentaje == 9.0
    assert carga_pension.monto_usd == round(pres.total_mano_obra_usd * 0.09, 2)

    # Debe consolidar la hoja de compras
    assert len(pres.hoja_compras) > 0
    cemento_item = next(h for h in pres.hoja_compras if "Cemento" in h.material)
    assert cemento_item.cantidad_requerida > 0

    # Total general debe ser subtotal + cargas
    assert pres.total_general_usd == round(pres.subtotal_usd + pres.total_cargas_usd, 2)
    assert pres.total_general_bs == round(pres.total_general_usd * 68.50, 2)

def test_sha256_anti_duplicates():
    data1 = b"fake invoice image 1"
    data2 = b"fake invoice image 1"
    data3 = b"fake invoice image 2"
    h1 = invoice_service.compute_sha256(data1)
    h2 = invoice_service.compute_sha256(data2)
    h3 = invoice_service.compute_sha256(data3)
    assert h1 == h2
    assert h1 != h3

if __name__ == "__main__":
    test_pared_bloque_calculation()
    test_pintura_calculation()
    test_ceramica_calculation()
    test_presupuesto_completo_con_ley_pensiones_y_consolidacion()
    test_sha256_anti_duplicates()
    print("¡Todos los tests unitarios pasaron exitosamente!")
