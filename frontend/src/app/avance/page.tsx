'use client';

import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Camera, 
  CheckCircle, 
  Clock, 
  ExternalLink, 
  Upload, 
  Layers, 
  Sparkles,
  Image as ImageIcon
} from 'lucide-react';
import { Obra, Partida, EvidenciaAvance } from '@/lib/types';
import { api } from '@/lib/api';
import { subscribeToTable } from '@/lib/supabase';
import { useAuth } from '@/lib/auth-context';

export default function AvancePage() {
  const { user } = useAuth();
  const [obras, setObras] = useState<Obra[]>([]);
  const [obraActiva, setObraActiva] = useState<Obra | null>(null);
  const [partidas, setPartidas] = useState<Partida[]>([]);
  const [evidencias, setEvidencias] = useState<EvidenciaAvance[]>([]);
  const [selectedPartida, setSelectedPartida] = useState<Partida | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // Modal subir evidencia
  const [showEvidenciaModal, setShowEvidenciaModal] = useState(false);
  const [evidenciaPartidaId, setEvidenciaPartidaId] = useState<string>('');
  const [evidenciaPorcentaje, setEvidenciaPorcentaje] = useState<string>('50');
  const [evidenciaNotas, setEvidenciaNotas] = useState<string>('');
  const [evidenciaFile, setEvidenciaFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadData = async () => {
    try {
      const list = await api.getObras(user?.id);
      setObras(list);
      const current = list[0] || null;
      setObraActiva(current);
      if (current) {
        const [parts, evids] = await Promise.all([
          api.getPartidas(current.id),
          api.getEvidencias(current.id)
        ]);
        setPartidas(parts);
        setEvidencias(evids);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();

    const unsubPartidas = subscribeToTable('partidas', () => {
      if (obraActiva) api.getPartidas(obraActiva.id).then(setPartidas);
    });
    const unsubEvid = subscribeToTable('evidencias_avance', () => {
      if (obraActiva) api.getEvidencias(obraActiva.id).then(setEvidencias);
    });

    return () => {
      unsubPartidas();
      unsubEvid();
    };
  }, []);

  // Cálculo de Avance Global Ponderado por monto de partida ($)
  const totalUsdPresupuestado = partidas.reduce((acc, p) => acc + (p.total_usd || 0), 0);
  const avanceGlobalPonderado = totalUsdPresupuestado > 0
    ? partidas.reduce((acc, p) => acc + (p.total_usd * (p.porcentaje_avance || 0)), 0) / totalUsdPresupuestado
    : 0;

  const handleUpdateAvance = async (partidaId: string, nuevoPorcentaje: number) => {
    setUpdatingId(partidaId);
    try {
      await api.updatePartidaAvance(partidaId, nuevoPorcentaje);
      setPartidas((prev) =>
        prev.map((p) => (p.id === partidaId ? { ...p, porcentaje_avance: nuevoPorcentaje } : p))
      );
    } catch (e) {
      console.error(e);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleSubmitEvidencia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!obraActiva || !evidenciaFile) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('obra_id', obraActiva.id);
      formData.append('partida_id', evidenciaPartidaId);
      formData.append('porcentaje', evidenciaPorcentaje);
      formData.append('notas', evidenciaNotas);
      formData.append('foto', evidenciaFile);

      await api.uploadEvidencia(formData);
      setShowEvidenciaModal(false);
      setEvidenciaFile(null);
      setEvidenciaNotas('');
      loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-orange-400 mb-1">
            <TrendingUp className="w-4 h-4" /> Avance Físico & Control de Partidas
          </div>
          <h1 className="text-2xl font-black text-white">
            {obraActiva ? obraActiva.nombre : 'Avance de Obra'}
          </h1>
          <p className="text-xs text-zinc-400">
            Control porcentual ponderado por partida (0–100%) con fotos de respaldo y trazabilidad en tiempo real
          </p>
        </div>

        <button
          onClick={() => {
            if (partidas.length > 0) setEvidenciaPartidaId(partidas[0].id);
            setShowEvidenciaModal(true);
          }}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs shadow-lg transition"
        >
          <Camera className="w-4 h-4" />
          <span>Subir Foto de Evidencia</span>
        </button>
      </div>

      {/* BARRA MAESTRA DE AVANCE GLOBAL PONDERADO */}
      <div className="p-6 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-orange-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> Avance Global Ponderado del Contrato
            </span>
            <p className="text-xs text-zinc-400 mt-0.5">
              Calculado matemáticamente con el peso financiero de cada partida sobre el total contratado
            </p>
          </div>

          <div className="text-right">
            <span className="text-3xl font-black font-mono text-white">
              {avanceGlobalPonderado.toFixed(1)}%
            </span>
            <span className="text-[10px] text-zinc-500 font-mono block">Completado Global</span>
          </div>
        </div>

        {/* Big Master Progress Bar */}
        <div className="w-full h-4 rounded-full bg-zinc-800 overflow-hidden relative p-0.5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-orange-600 via-amber-500 to-emerald-500 transition-all duration-700 shadow-md"
            style={{ width: `${Math.min(100, Math.max(0, avanceGlobalPonderado))}%` }}
          />
        </div>
      </div>

      {/* LISTA DE PARTIDAS CON BARRAS INDIVIDUALES 0-100% */}
      <div className="space-y-4">
        <span className="text-xs font-bold text-white uppercase tracking-wider block">
          Partidas Individuales ({partidas.length})
        </span>

        <div className="grid grid-cols-1 gap-4">
          {partidas.length === 0 ? (
            <div className="p-12 text-center text-zinc-500 rounded-2xl border border-zinc-800 bg-[#0a0f1d] text-xs">
              No hay partidas registradas en esta obra.
            </div>
          ) : (
            partidas.map((p) => {
              const pct = p.porcentaje_avance || 0;
              const evidenciasDePartida = evidencias.filter((e) => e.partida_id === p.id);

              return (
                <div
                  key={p.id}
                  className="p-5 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-lg hover:border-zinc-700 transition space-y-4"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">{p.descripcion}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                          {p.tipo_partida}
                        </span>
                      </div>
                      <span className="text-xs text-zinc-500 font-mono mt-0.5 block">
                        Presupuesto: ${p.total_usd.toFixed(2)} ({p.area ? `${p.area} m²` : `${p.cantidad} ${p.unidad}`})
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-xl font-black font-mono text-white">{pct.toFixed(0)}%</span>
                        <span className="text-[10px] text-zinc-500 block">Completitud</span>
                      </div>

                      {/* Quick percentage adjustment buttons */}
                      <div className="flex items-center gap-1">
                        {[0, 25, 50, 75, 100].map((step) => (
                          <button
                            key={step}
                            onClick={() => handleUpdateAvance(p.id, step)}
                            disabled={updatingId === p.id}
                            className={`px-2 py-1 rounded text-[11px] font-mono font-bold transition ${
                              pct === step
                                ? 'bg-orange-600 text-white'
                                : 'bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700'
                            }`}
                          >
                            {step}%
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Individual Progress Bar */}
                  <div className="space-y-1">
                    <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          pct === 100 ? 'bg-emerald-500' : pct > 40 ? 'bg-orange-500' : 'bg-amber-500'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>

                  {/* Fotos de respaldo adjuntas a esta partida */}
                  {evidenciasDePartida.length > 0 && (
                    <div className="pt-2 border-t border-zinc-800/80">
                      <span className="text-[11px] font-semibold text-zinc-400 mb-2 flex items-center gap-1.5">
                        <ImageIcon className="w-3.5 h-3.5 text-zinc-500" />
                        Fotos de Respaldo ({evidenciasDePartida.length})
                      </span>
                      <div className="flex items-center gap-3 overflow-x-auto pb-1">
                        {evidenciasDePartida.map((ev) => (
                          <a
                            key={ev.id}
                            href={ev.foto_url}
                            target="_blank"
                            rel="noreferrer"
                            className="relative group shrink-0 w-24 h-20 rounded-xl overflow-hidden border border-zinc-700 bg-black block"
                          >
                            <img
                              src={ev.foto_url}
                              alt="Evidencia"
                              className="w-full h-full object-cover group-hover:scale-110 transition duration-300"
                            />
                            <div className="absolute inset-0 bg-black/40 group-hover:bg-black/10 transition flex items-center justify-center">
                              <span className="text-[10px] font-bold text-white px-1.5 py-0.5 rounded bg-black/70">
                                {ev.porcentaje_alcanzado}%
                              </span>
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Modal Subir Foto Evidencia */}
      {showEvidenciaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0f172a] border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white mb-4">Subir Evidencia Fotográfica de Avance</h3>
            <form onSubmit={handleSubmitEvidencia} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">Partida a Actualizar</label>
                <select
                  value={evidenciaPartidaId}
                  onChange={(e) => setEvidenciaPartidaId(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-xs text-white"
                >
                  {partidas.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.descripcion} (Actual: {p.porcentaje_avance}%)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">
                  Nuevo % de Avance Alcanzado (0–100%):
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  required
                  value={evidenciaPorcentaje}
                  onChange={(e) => setEvidenciaPorcentaje(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">Foto de Obra</label>
                <input
                  type="file"
                  accept="image/*"
                  required
                  onChange={(e) => e.target.files && setEvidenciaFile(e.target.files[0])}
                  className="w-full text-xs text-zinc-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-zinc-800 file:text-white hover:file:bg-zinc-700"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1">Notas de Inspección</label>
                <input
                  type="text"
                  value={evidenciaNotas}
                  onChange={(e) => setEvidenciaNotas(e.target.value)}
                  placeholder="Ej. Frisado finalizado, listo para pintar"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-xs text-white"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowEvidenciaModal(false)}
                  className="flex-1 py-2 rounded-xl bg-zinc-800 text-zinc-400 hover:text-white text-xs font-semibold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  className="flex-1 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold"
                >
                  {uploading ? 'Subiendo...' : 'Guardar y Actualizar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
