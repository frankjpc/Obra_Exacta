'use client';

import React, { useState, useEffect } from 'react';
import { 
  Calculator, 
  Plus, 
  Layers, 
  Package, 
  TrendingUp, 
  ShieldAlert, 
  Edit2, 
  Check, 
  RefreshCw,
  HardHat,
  FileText,
  Download,
  Brain,
  History,
  X
} from 'lucide-react';
import { Obra, Partida, HojaComprasItem, CargaFiscal, CatalogoPrecioUsuario, HistorialEdicion } from '@/lib/types';
import { api } from '@/lib/api';
import { subscribeToTable } from '@/lib/supabase';
import { useAuth } from '@/lib/auth-context';

export default function PresupuestosPage() {
  const { user } = useAuth();
  const [obras, setObras] = useState<Obra[]>([]);
  const [obraActiva, setObraActiva] = useState<Obra | null>(null);
  const [partidas, setPartidas] = useState<Partida[]>([]);
  const [hojaCompras, setHojaCompras] = useState<HojaComprasItem[]>([]);
  const [memoriaPrecios, setMemoriaPrecios] = useState<CatalogoPrecioUsuario[]>([]);
  const [historialEdiciones, setHistorialEdiciones] = useState<HistorialEdicion[]>([]);
  const [activeTab, setActiveTab] = useState<'tabla' | 'compras'>('tabla');
  const [loading, setLoading] = useState(true);
  const [showMemoriaModal, setShowMemoriaModal] = useState(false);

  // Edición rápida de partida
  const [editingPartidaId, setEditingPartidaId] = useState<string | null>(null);
  const [editPUnit, setEditPUnit] = useState<string>('');

  // Nueva partida manual
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTipo, setNewTipo] = useState('pared_bloque');
  const [newDesc, setNewDesc] = useState('');
  const [newLargo, setNewLargo] = useState('6.0');
  const [newAlto, setNewAlto] = useState('2.8');
  const [newCant, setNewCant] = useState('1');

  const loadData = async () => {
    try {
      const list = await api.getObras(user?.id);
      setObras(list);
      const current = list[0] || null;
      setObraActiva(current);
      if (current) {
        const [parts, hoja, memoria, hist] = await Promise.all([
          api.getPartidas(current.id),
          api.getHojaCompras(current.id),
          api.getMemoriaPrecios(user?.id),
          api.getHistorialEdiciones(current.id)
        ]);
        setPartidas(parts);
        setHojaCompras(hoja);
        setMemoriaPrecios(memoria);
        setHistorialEdiciones(hist);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Suscripción a Realtime de Supabase
    const unsubPartidas = subscribeToTable('partidas', () => {
      if (obraActiva) api.getPartidas(obraActiva.id).then(setPartidas);
    });
    const unsubHoja = subscribeToTable('hoja_compras', () => {
      if (obraActiva) api.getHojaCompras(obraActiva.id).then(setHojaCompras);
    });

    return () => {
      unsubPartidas();
      unsubHoja();
    };
  }, []);

  const tasaBcv = obraActiva?.tasa_bcv || 68.50;

  // Cálculos bimonetarios automáticos de la tabla
  const subtotalUsd = partidas.reduce((acc, p) => acc + (p.total_usd || 0), 0);
  const subtotalBs = subtotalUsd * tasaBcv;

  // Carga Fiscal: 9% Ley de Protección de Pensiones sobre Mano de Obra
  // Asumiendo ~35% de componente de mano de obra en el total
  const manoDeObraEstimadaUsd = subtotalUsd * 0.35;
  const pensionUsd = manoDeObraEstimadaUsd * 0.09;
  const pensionBs = pensionUsd * tasaBcv;

  // Indirectos / Imprevistos (10%)
  const indirectosUsd = subtotalUsd * 0.10;
  const indirectosBs = indirectosUsd * tasaBcv;

  const totalGeneralUsd = subtotalUsd + pensionUsd + indirectosUsd;
  const totalGeneralBs = totalGeneralUsd * tasaBcv;

  const handleCrearPartida = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!obraActiva) return;
    try {
      await api.addPartida(obraActiva.id, {
        tipo_partida: newTipo as any,
        descripcion: newDesc || undefined,
        largo: parseFloat(newLargo) || 0,
        alto: parseFloat(newAlto) || 0,
        cantidad: parseFloat(newCant) || 1
      });
      setShowAddModal(false);
      setNewDesc('');
      const parts = await api.getPartidas(obraActiva.id);
      setPartidas(parts);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title & Stats */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-orange-400 mb-1">
            <Calculator className="w-4 h-4" /> Presupuestos Tabulados 2D • Norma COVENIN
          </div>
          <h1 className="text-2xl font-black text-white">
            {obraActiva ? obraActiva.nombre : 'Presupuesto de Obra'}
          </h1>
          <p className="text-xs text-zinc-400">
            Tabla bimonetaria estricta de 7 columnas según código COVENIN y rendimientos tabulados venezolanos
          </p>
          
          {/* Badge informativo de Memoria Operativa Activa */}
          <div className="flex flex-wrap items-center gap-3 pt-3">
            <button
              onClick={() => setShowMemoriaModal(true)}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border border-purple-800/60 bg-purple-950/30 hover:bg-purple-900/40 text-purple-300 text-xs font-medium transition cursor-pointer shadow-sm"
              title="Ver memoria de precios aprendidos del contratista e historial de modificaciones"
            >
              <Brain className="w-4 h-4 text-purple-400" />
              <span>Memoria Operativa Activa: <strong className="text-white">{memoriaPrecios.length} precios personalizados</strong> guardados</span>
              <span className="text-[10px] bg-purple-900/70 text-purple-200 px-1.5 py-0.5 rounded-full font-semibold">Ver memoria</span>
            </button>
            {historialEdiciones.length > 0 && (
              <span className="text-xs text-zinc-500 flex items-center gap-1.5 font-mono">
                <History className="w-3.5 h-3.5 text-zinc-400" />
                {historialEdiciones.length} cambios conversacionales registrados
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {obraActiva && (
            <a
              href={api.getPresupuestoPdfUrl(obraActiva.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 font-semibold text-xs shadow-md transition"
              title="Descargar presupuesto formal en PDF de 7 columnas listo para cliente"
            >
              <Download className="w-4 h-4 text-orange-400" />
              <span>Descargar PDF (7 Col)</span>
            </a>
          )}
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs shadow-lg transition"
          >
            <Plus className="w-4 h-4" />
            <span>Agregar Partida Manual</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800 gap-6">
        <button
          onClick={() => setActiveTab('tabla')}
          className={`pb-3 text-sm font-bold flex items-center gap-2 border-b-2 transition ${
            activeTab === 'tabla'
              ? 'border-orange-500 text-orange-400'
              : 'border-transparent text-zinc-400 hover:text-white'
          }`}
        >
          <Layers className="w-4 h-4" />
          Tabla de Partidas (7 Columnas COVENIN)
          <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
            {partidas.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('compras')}
          className={`pb-3 text-sm font-bold flex items-center gap-2 border-b-2 transition ${
            activeTab === 'compras'
              ? 'border-orange-500 text-orange-400'
              : 'border-transparent text-zinc-400 hover:text-white'
          }`}
        >
          <Package className="w-4 h-4" />
          Hoja de Compras Estimada (Consolidada)
          <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
            {hojaCompras.length} materiales
          </span>
        </button>
      </div>

      {activeTab === 'tabla' ? (
        <div className="space-y-6">
          {/* TABLA DE 7 COLUMNAS COVENIN BIMONETARIAS */}
          <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-xl">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/90 text-zinc-400 uppercase tracking-wider font-bold">
                  <th className="py-3.5 px-3 w-32">Cód. COVENIN</th>
                  <th className="py-3.5 px-4 w-2/5">1. Partida / Descripción</th>
                  <th className="py-3.5 px-3 text-center">2. Unidad</th>
                  <th className="py-3.5 px-3 text-right">3. P. Unit ($)</th>
                  <th className="py-3.5 px-4 text-right font-bold text-white bg-zinc-800/40">4. Total ($)</th>
                  <th className="py-3.5 px-3 text-right text-emerald-400">5. P. Unit (Bs)</th>
                  <th className="py-3.5 px-4 text-right font-bold text-emerald-400 bg-emerald-950/20">6. Total (Bs)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 font-mono">
                {partidas.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-zinc-500 font-sans">
                      No hay partidas registradas en esta obra. Envía una nota de voz por Telegram o usa "Voz / Cuantificar".
                    </td>
                  </tr>
                ) : (
                  partidas.map((p, idx) => (
                    <tr key={p.id || idx} className="hover:bg-zinc-800/40 transition-colors">
                      <td className="py-3 px-3">
                        <span className="inline-block font-mono text-[11px] font-bold text-orange-400 bg-orange-950/50 border border-orange-800/50 px-2 py-0.5 rounded">
                          {p.codigo_covenin || 'E-GEN.000.001'}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-sans font-medium text-zinc-200">
                        <div className="font-semibold text-white">{p.descripcion}</div>
                        <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                          {p.tipo_partida} • {p.area ? `${p.area.toFixed(2)} m²` : `${p.cantidad} ${p.unidad}`}
                          {p.largo && p.alto ? ` (${p.largo}m × ${p.alto}m)` : ''}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center text-zinc-400 font-semibold">{p.unidad}</td>
                      <td className="py-3 px-3 text-right text-zinc-300">${p.p_unit_usd.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right font-bold text-white bg-zinc-800/20">
                        ${p.total_usd.toFixed(2)}
                      </td>
                      <td className="py-3 px-3 text-right text-emerald-400/90 font-medium">
                        {(p.p_unit_usd * tasaBcv).toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-emerald-400 bg-emerald-950/10">
                        {(p.total_usd * tasaBcv).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* BLOQUE EDITABLE DE CARGAS FISCALES E INDIRECTOS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl border border-zinc-800 bg-[#0a0f1d] space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-orange-400 uppercase tracking-wider">
                <ShieldAlert className="w-4 h-4" /> Bloque de Cargas Fiscales e Indirectos
              </div>
              <p className="text-xs text-zinc-400">
                Leyes vigentes y coeficientes indirectos aplicados sobre la estructura de costos de la obra.
              </p>

              <div className="space-y-2 pt-2 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-900 border border-zinc-800">
                  <div>
                    <span className="font-semibold text-white">Ley de Protección de Pensiones</span>
                    <span className="text-[10px] text-zinc-500 block">9% sobre componente de Mano de Obra</span>
                  </div>
                  <div className="text-right font-mono">
                    <span className="font-bold text-white">${pensionUsd.toFixed(2)}</span>
                    <span className="text-[11px] text-emerald-400 block">Bs. {pensionBs.toLocaleString()}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-900 border border-zinc-800">
                  <div>
                    <span className="font-semibold text-white">Gastos de Administración e Imprevistos</span>
                    <span className="text-[10px] text-zinc-500 block">10% s/ Subtotal directo</span>
                  </div>
                  <div className="text-right font-mono">
                    <span className="font-bold text-white">${indirectosUsd.toFixed(2)}</span>
                    <span className="text-[11px] text-emerald-400 block">Bs. {indirectosBs.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* TOTALES CONSOLIDADOS */}
            <div className="p-5 rounded-2xl border border-orange-600/30 bg-gradient-to-br from-orange-950/20 to-zinc-900/60 flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-orange-400">Resumen Bimonetario Consolidado</span>
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between text-zinc-400">
                    <span>Subtotal Partidas 2D:</span>
                    <span className="font-mono text-zinc-200">${subtotalUsd.toFixed(2)} (Bs. {subtotalBs.toLocaleString()})</span>
                  </div>
                  <div className="flex justify-between text-zinc-400">
                    <span>Total Cargas Fiscales:</span>
                    <span className="font-mono text-zinc-200">${(pensionUsd + indirectosUsd).toFixed(2)}</span>
                  </div>
                  <div className="h-px bg-zinc-800 my-2" />
                </div>
              </div>

              <div className="pt-4 border-t border-zinc-800/80">
                <span className="text-xs text-zinc-400 block">PRESUPUESTO TOTAL GENERAL</span>
                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-3xl font-black text-white font-mono tracking-tight">
                    ${totalGeneralUsd.toFixed(2)}
                  </span>
                  <span className="text-base font-bold text-emerald-400 font-mono">
                    Bs. {totalGeneralBs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-500 font-mono mt-1 block">
                  Tasa oficial de referencia: {tasaBcv.toFixed(2)} Bs/USD
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* HOJA DE COMPRAS CONSOLIDADA */
        <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-xl">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/90 text-zinc-400 uppercase tracking-wider font-bold">
                <th className="py-3.5 px-4">Material Consolidado</th>
                <th className="py-3.5 px-3 text-center">Unidad</th>
                <th className="py-3.5 px-3 text-right">Cant. Requerida</th>
                <th className="py-3.5 px-3 text-right text-emerald-400">Cant. Comprada</th>
                <th className="py-3.5 px-3 text-right">P. Unit Estimado ($)</th>
                <th className="py-3.5 px-4 text-right font-bold text-white">Total Estimado ($)</th>
                <th className="py-3.5 px-3 text-center">Estatus</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono">
              {hojaCompras.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-sans">
                    No hay materiales consolidados. Se generarán automáticamente al crear partidas.
                  </td>
                </tr>
              ) : (
                hojaCompras.map((m, idx) => {
                  const completitud = m.cantidad_requerida > 0 ? (m.cantidad_comprada / m.cantidad_requerida) * 100 : 0;
                  return (
                    <tr key={m.id || idx} className="hover:bg-zinc-800/40 transition-colors">
                      <td className="py-3 px-4 font-sans font-semibold text-white">{m.material}</td>
                      <td className="py-3 px-3 text-center text-zinc-400">{m.unidad}</td>
                      <td className="py-3 px-3 text-right font-bold text-zinc-200">{m.cantidad_requerida}</td>
                      <td className="py-3 px-3 text-right font-bold text-emerald-400">{m.cantidad_comprada}</td>
                      <td className="py-3 px-3 text-right text-zinc-400">${m.p_unit_estimado_usd.toFixed(2)}</td>
                      <td className="py-3 px-4 text-right font-bold text-white">${m.total_estimado_usd.toFixed(2)}</td>
                      <td className="py-3 px-3 text-center font-sans">
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          completitud >= 100 
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' 
                            : completitud > 0 
                            ? 'bg-amber-950 text-amber-400 border border-amber-800' 
                            : 'bg-zinc-800 text-zinc-400'
                        }`}>
                          {completitud >= 100 ? 'Comprado' : completitud > 0 ? `${completitud.toFixed(0)}%` : 'Pendiente'}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal Agregar Partida Manual */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0f172a] border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-4">Agregar Partida 2D Manual</h3>
            <form onSubmit={handleCrearPartida} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">Tipo de Partida Tabulada</label>
                <select
                  value={newTipo}
                  onChange={(e) => setNewTipo(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-xs text-white"
                >
                  <option value="pared_bloque">Pared de Bloque 15cm (14 bloq/m2, 0.08m3 arena, 0.35 sacos)</option>
                  <option value="pintura">Pintura Caucho 2 Manos (0.04 gal/m2)</option>
                  <option value="ceramica">Cerámica / Porcelanato (1.05 m2 + 0.25 sacos pego)</option>
                  <option value="cielo_raso">Cielo Raso Yeso + Perfilería</option>
                  <option value="lampara">Lámpara LED / Luminaria (Unitaria)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">Descripción</label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Ej. Tabiquería divisoria oficina gerencia"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 mb-1">Largo (m)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={newLargo}
                    onChange={(e) => setNewLargo(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 mb-1">Alto (m)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={newAlto}
                    onChange={(e) => setNewAlto(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 mb-1">Cantidad</label>
                  <input
                    type="number"
                    step="1"
                    value={newCant}
                    onChange={(e) => setNewCant(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white font-mono"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 py-2 rounded-xl bg-zinc-800 text-zinc-400 hover:text-white text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold"
                >
                  Calcular y Guardar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Memoria Operativa del Contratista & Historial de Ediciones */}
      {showMemoriaModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b101e] border border-zinc-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl">
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Brain className="w-5 h-5 text-purple-400" />
                <div>
                  <h3 className="text-sm font-bold text-white">Memoria Operativa de Precios</h3>
                  <p className="text-[11px] text-zinc-400">Precios personalizados aprendidos y aplicados automáticamente en futuros cálculos</p>
                </div>
              </div>
              <button 
                onClick={() => setShowMemoriaModal(false)}
                className="p-1 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
              {/* Sección 1: Catálogo de Precios Guardados */}
              <div>
                <h4 className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <Package className="w-3.5 h-3.5" /> Precios Personalizados Vigentes ({memoriaPrecios.length})
                </h4>
                {memoriaPrecios.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-zinc-800 text-center text-xs text-zinc-500">
                    Aún no hay precios personalizados guardados. Puedes pedirle al Bot por Telegram ej. <em>"cámbiale el precio de la pintura a 8 dólares"</em> o <em>"sube el bloque a 1.35 con Ferretería Los Guayos"</em>.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    {memoriaPrecios.map((item, idx) => (
                      <div key={item.id || idx} className="p-3 rounded-xl bg-zinc-900/90 border border-zinc-800 flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-white">{item.nombre}</div>
                          <div className="text-[10px] text-zinc-500 font-mono">
                            Clave: {item.clave_o_codigo} {item.proveedor_opcional ? `• ${item.proveedor_opcional}` : ''}
                          </div>
                        </div>
                        <div className="text-right font-mono">
                          <div className="font-bold text-emerald-400">${item.precio_usd.toFixed(2)}</div>
                          <div className="text-[10px] text-zinc-500">/{item.unidad}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Sección 2: Historial de Ediciones Conversacionales */}
              <div>
                <h4 className="text-xs font-bold text-orange-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <History className="w-3.5 h-3.5" /> Historial de Cambios por Chat ({historialEdiciones.length})
                </h4>
                {historialEdiciones.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-zinc-800 text-center text-xs text-zinc-500">
                    Sin ediciones conversacionales recientes.
                  </div>
                ) : (
                  <div className="space-y-2 text-xs font-mono">
                    {historialEdiciones.map((h, idx) => (
                      <div key={h.id || idx} className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 flex items-center justify-between">
                        <div>
                          <div className="text-zinc-300 font-sans font-medium">{h.accion.replace('_', ' ').toUpperCase()} • {h.partida_o_material}</div>
                          <div className="text-[10px] text-zinc-500">
                            Anterior: {h.valor_anterior || 'Base'} ➔ Nuevo: <span className="text-orange-400 font-bold">{h.valor_nuevo}</span>
                          </div>
                        </div>
                        <div className="text-[10px] text-zinc-500">
                          {h.created_at ? new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Reciente'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setShowMemoriaModal(false)}
                className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
