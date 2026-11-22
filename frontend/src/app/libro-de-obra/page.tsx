'use client';

import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Share2, 
  Plus, 
  Copy, 
  Check, 
  ExternalLink,
  DollarSign,
  TrendingUp,
  ShieldCheck
} from 'lucide-react';
import { Obra, LibroObraItem } from '@/lib/types';
import { api } from '@/lib/api';
import { subscribeToTable } from '@/lib/supabase';
import { useAuth } from '@/lib/auth-context';
import IncidentUploadModal from '@/components/IncidentUploadModal';

export default function LibroDeObraPage() {
  const { user } = useAuth();
  const [obras, setObras] = useState<Obra[]>([]);
  const [obraActiva, setObraActiva] = useState<Obra | null>(null);
  const [incidencias, setIncidencias] = useState<LibroObraItem[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const list = await api.getObras(user?.id);
      setObras(list);
      const current = list[0] || null;
      setObraActiva(current);
      if (current) {
        const items = await api.getLibroObra(current.id);
        setIncidencias(items);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();

    const unsub = subscribeToTable('libro_obra', () => {
      if (obraActiva) api.getLibroObra(obraActiva.id).then(setIncidencias);
    });

    return () => unsub();
  }, []);

  const copyLink = (token: string) => {
    const url = `${window.location.origin}/aprobar/${token}`;
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const totalAdicionalesUsd = incidencias.reduce((acc, it) => acc + (it.costo_adicional_usd || 0), 0);
  const totalAprobadosUsd = incidencias
    .filter((it) => it.estado_aprobacion === 'aprobado')
    .reduce((acc, it) => acc + (it.costo_adicional_usd || 0), 0);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400 mb-1">
            <FileText className="w-4 h-4" /> Libro de Obra Digital & Control de Imprevistos
          </div>
          <h1 className="text-2xl font-black text-white">
            {obraActiva ? obraActiva.nombre : 'Libro de Obra'}
          </h1>
          <p className="text-xs text-zinc-400">
            Bitácora de paradas por vicios ocultos, % de variación contractual y aprobación móvil para clientes
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-semibold text-xs shadow-lg transition"
        >
          <Plus className="w-4 h-4" />
          <span>Reportar Parada / Daño Oculto</span>
        </button>
      </div>

      {/* METRICAS DE VARIACION */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-lg">
          <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Paradas Registradas</span>
          <div className="text-2xl font-black text-white font-mono mt-1">
            {incidencias.length}
          </div>
          <span className="text-xs text-zinc-400 mt-1 block">
            {incidencias.filter(i => i.estado_aprobacion === 'pendiente').length} pendientes de firma
          </span>
        </div>

        <div className="p-5 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-lg">
          <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Total Adicionales Reclamados</span>
          <div className="text-2xl font-black text-amber-400 font-mono mt-1">
            ${totalAdicionalesUsd.toFixed(2)}
          </div>
          <span className="text-xs text-zinc-400 mt-1 block font-mono">
            Bs. {(totalAdicionalesUsd * (obraActiva?.tasa_bcv || 68.50)).toLocaleString()}
          </span>
        </div>

        <div className="p-5 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-lg">
          <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Adicionales Aprobados</span>
          <div className="text-2xl font-black text-emerald-400 font-mono mt-1">
            ${totalAprobadosUsd.toFixed(2)}
          </div>
          <span className="text-xs text-emerald-500 mt-1 block flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" /> Sumados al presupuesto contractual
          </span>
        </div>
      </div>

      {/* LISTA DE INCIDENCIAS */}
      <div className="rounded-2xl border border-zinc-800 bg-[#0a0f1d] overflow-hidden shadow-xl">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            Bitácora de Incidencias y Paradas ({incidencias.length})
          </span>
          <span className="text-xs text-zinc-400">
            Sincronización en vivo con Telegram
          </span>
        </div>

        <div className="divide-y divide-zinc-800/60">
          {incidencias.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-xs">
              No hay paradas ni daños ocultos registrados en esta obra.
            </div>
          ) : (
            incidencias.map((item) => {
              const esAprobado = item.estado_aprobacion === 'aprobado';
              const publicUrl = `${typeof window !== 'undefined' ? window.location.origin : ''}/aprobar/${item.token_aprobacion}`;

              return (
                <div key={item.id} className="p-5 hover:bg-zinc-800/30 transition flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-3 rounded-2xl border shrink-0 ${
                      esAprobado
                        ? 'bg-emerald-950/40 border-emerald-800 text-emerald-400'
                        : 'bg-red-950/40 border-red-800 text-red-400'
                    }`}>
                      {esAprobado ? <CheckCircle2 className="w-6 h-6" /> : <AlertTriangle className="w-6 h-6" />}
                    </div>

                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-white text-base">{item.titulo}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                          esAprobado
                            ? 'bg-emerald-950 border border-emerald-800 text-emerald-300'
                            : 'bg-amber-950 border border-amber-800 text-amber-300 animate-pulse'
                        }`}>
                          {esAprobado ? 'Aprobado por el Cliente' : 'Pendiente de Aprobación'}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 font-mono text-amber-400 font-bold">
                          +{item.porcentaje_variacion}% contrato
                        </span>
                      </div>

                      <p className="text-xs text-zinc-300 leading-relaxed max-w-2xl">
                        {item.descripcion}
                      </p>

                      <div className="flex items-center gap-4 text-xs font-mono text-zinc-400 pt-1">
                        <span>Costo Adicional: <strong className="text-white">${item.costo_adicional_usd.toFixed(2)}</strong> (Bs. {item.costo_adicional_bs ? item.costo_adicional_bs.toLocaleString() : (item.costo_adicional_usd * 68.5).toLocaleString()})</span>
                        {item.aprobado_en && (
                          <span className="text-emerald-400 font-sans">
                            Firma: {item.cliente_nombre || 'Cliente'} ({new Date(item.aprobado_en).toLocaleDateString()})
                          </span>
                        )}
                      </div>

                      {item.foto_url && (
                        <div className="pt-2">
                          <a
                            href={item.foto_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs text-orange-400 hover:text-orange-300 underline"
                          >
                            <ExternalLink className="w-3.5 h-3.5" /> Ver foto del daño oculto
                          </a>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Acciones y enlace de aprobación */}
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <button
                      onClick={() => copyLink(item.token_aprobacion)}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold border border-zinc-700 transition"
                      title="Copiar enlace móvil para el cliente"
                    >
                      {copiedToken === item.token_aprobacion ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-400">¡Enlace Copiado!</span>
                        </>
                      ) : (
                        <>
                          <Share2 className="w-3.5 h-3.5 text-orange-400" />
                          <span>Copiar Link Móvil</span>
                        </>
                      )}
                    </button>

                    <a
                      href={`/aprobar/${item.token_aprobacion}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-zinc-500 hover:text-zinc-300 flex items-center gap-1"
                    >
                      Abrir vista de cliente <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {showModal && obraActiva && (
        <IncidentUploadModal
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          obraId={obraActiva.id}
          presupuestoBaseUsd={obraActiva.presupuesto_total_usd || 0}
          onSuccess={() => {
            setShowModal(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}
