'use client';

import React, { useState, useEffect } from 'react';
import { 
  ShoppingCart, 
  AlertOctagon, 
  ShieldCheck, 
  FileText, 
  Plus, 
  TrendingDown, 
  Calendar, 
  DollarSign,
  ExternalLink,
  Tag
} from 'lucide-react';
import { Obra, Factura } from '@/lib/types';
import { api } from '@/lib/api';
import { subscribeToTable } from '@/lib/supabase';
import { useAuth } from '@/lib/auth-context';
import InvoiceUploadModal from '@/components/InvoiceUploadModal';

export default function ComprasPage() {
  const { user } = useAuth();
  const [obras, setObras] = useState<Obra[]>([]);
  const [obraActiva, setObraActiva] = useState<Obra | null>(null);
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFactura, setSelectedFactura] = useState<Factura | null>(null);

  const loadData = async () => {
    try {
      const list = await api.getObras(user?.id);
      setObras(list);
      const current = list[0] || null;
      setObraActiva(current);
      if (current) {
        const facs = await api.getFacturas(current.id);
        setFacturas(facs);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();

    // Supabase Realtime para facturas
    const unsub = subscribeToTable('facturas', () => {
      if (obraActiva) api.getFacturas(obraActiva.id).then(setFacturas);
    });

    return () => unsub();
  }, []);

  const presUsd = obraActiva?.presupuesto_total_usd || 0;
  const gastUsd = facturas.reduce((acc, f) => acc + (f.total_usd || 0), 0);
  const dispUsd = Math.max(0, presUsd - gastUsd);
  const pctGastado = presUsd > 0 ? Math.min(100, (gastUsd / presUsd) * 100) : 0;
  const alertasCriticas = facturas.filter(f => f.alerta_sobreprecio || f.alerta_fuera_partida || f.alerta_duplicada);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-1">
            <ShoppingCart className="w-4 h-4" /> Control de Compras & Auditoría de Gastos
          </div>
          <h1 className="text-2xl font-black text-white">
            {obraActiva ? obraActiva.nombre : 'Compras de Obra'}
          </h1>
          <p className="text-xs text-zinc-400">
            Deducción presupuestaria automática, control de sobreprecio y detección anti-duplicados SHA-256
          </p>
        </div>

        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-lg transition"
        >
          <Plus className="w-4 h-4" />
          <span>Subir Factura de Ferretería</span>
        </button>
      </div>

      {/* BARRA DE PRESUPUESTADO VS GASTADO REAL */}
      <div className="p-6 rounded-2xl border border-zinc-800 bg-[#0a0f1d] shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Ejecución Presupuestaria de Compras
            </span>
            <div className="flex items-baseline gap-3 mt-1">
              <span className="text-2xl font-black text-white font-mono">
                ${gastUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="text-xs text-zinc-400 font-mono">
                de ${presUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} presupuestados
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="text-right">
              <span className="text-zinc-500 block text-[10px] uppercase font-sans">Margen Restante</span>
              <span className="text-sm font-bold text-emerald-400 font-mono">
                ${dispUsd.toFixed(2)}
              </span>
            </div>
            <div className="h-8 w-px bg-zinc-800" />
            <div className="text-right">
              <span className="text-zinc-500 block text-[10px] uppercase font-sans">Porcentaje Consumido</span>
              <span className={`text-sm font-bold font-mono ${pctGastado > 85 ? 'text-red-400' : 'text-zinc-200'}`}>
                {pctGastado.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Progress Meter */}
        <div className="w-full h-3 rounded-full bg-zinc-800 overflow-hidden relative">
          <div 
            className={`h-full transition-all duration-500 rounded-full ${
              pctGastado > 90 ? 'bg-red-500' : pctGastado > 70 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${pctGastado}%` }}
          />
        </div>
      </div>

      {/* ALERTA DE FUGAS / SOBREPRECIO SI EXISTEN */}
      {alertasCriticas.length > 0 && (
        <div className="p-4 rounded-2xl bg-red-950/40 border border-red-800/80 flex items-start gap-3">
          <AlertOctagon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-bold text-red-300">
              {alertasCriticas.length} Factura(s) con Alertas de Sobreprecio o Ítems Fuera de Partida:
            </span>
            <ul className="list-disc list-inside mt-1 text-red-200 space-y-0.5">
              {alertasCriticas.map((a, i) => (
                <li key={i}>
                  <strong className="text-white">{a.proveedor}:</strong> {a.detalle_alerta || 'Alerta detectada en auditoría'}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* HISTORIAL DE FACTURAS */}
      <div className="rounded-2xl border border-zinc-800 bg-[#0a0f1d] overflow-hidden shadow-xl">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            Historial de Facturas y Compras ({facturas.length})
          </span>
          <span className="text-xs text-zinc-400 font-mono">
            Anti-duplicados SHA-256 Activo
          </span>
        </div>

        <div className="divide-y divide-zinc-800/60">
          {facturas.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-xs">
              No hay facturas registradas en esta obra. Sube una foto o envíala al bot de Telegram.
            </div>
          ) : (
            facturas.map((f) => {
              const tieneAlerta = f.alerta_sobreprecio || f.alerta_fuera_partida || f.alerta_duplicada;
              return (
                <div 
                  key={f.id} 
                  className={`p-4 hover:bg-zinc-800/30 transition flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                    tieneAlerta ? 'bg-red-950/10' : ''
                  }`}
                >
                  <div className="flex items-start gap-3.5">
                    <div className={`p-2.5 rounded-xl border shrink-0 ${
                      tieneAlerta 
                        ? 'bg-red-950/50 border-red-800 text-red-400' 
                        : 'bg-zinc-900 border-zinc-700 text-emerald-400'
                    }`}>
                      {tieneAlerta ? <AlertOctagon className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">{f.proveedor}</span>
                        {f.nro_control && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-400">
                            {f.nro_control}
                          </span>
                        )}
                        {tieneAlerta && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-red-950 border border-red-800 text-red-300 font-bold">
                            Alerta Roja
                          </span>
                        )}
                      </div>

                      <div className="text-xs text-zinc-400 flex items-center gap-3 mt-1 font-mono">
                        <span className="flex items-center gap-1 font-sans">
                          <Calendar className="w-3.5 h-3.5 text-zinc-500" /> {f.fecha}
                        </span>
                        {f.hash_sha256 && (
                          <span className="text-zinc-500 text-[10px]">
                            SHA: {f.hash_sha256.slice(0, 10)}...
                          </span>
                        )}
                      </div>

                      {f.detalle_alerta && tieneAlerta && (
                        <p className="text-xs text-red-300 mt-1 font-medium bg-red-950/40 p-1.5 rounded-lg border border-red-900/40">
                          {f.detalle_alerta}
                        </p>
                      )}

                      {/* Items preview */}
                      {f.items && f.items.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {f.items.map((it, idx) => (
                            <span key={idx} className="text-[11px] px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                              {it.descripcion} ({it.cantidad} uds)
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-base font-bold font-mono text-white block">
                      ${f.total_usd.toFixed(2)}
                    </span>
                    <span className="text-xs font-mono text-emerald-400 block">
                      Bs. {f.total_bs ? f.total_bs.toLocaleString() : (f.total_usd * (obraActiva?.tasa_bcv || 68.50)).toLocaleString()}
                    </span>
                    {f.foto_url && (
                      <a
                        href={f.foto_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] text-orange-400 hover:text-orange-300 inline-flex items-center gap-1 mt-1 underline"
                      >
                        <ExternalLink className="w-3 h-3" /> Ver comprobante
                      </a>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {showUploadModal && obraActiva && (
        <InvoiceUploadModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          obraId={obraActiva.id}
          onSuccess={() => {
            setShowUploadModal(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}
