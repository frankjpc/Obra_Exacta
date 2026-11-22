'use client';

import React, { useState } from 'react';
import { 
  Building2, 
  DollarSign, 
  Mic, 
  Upload, 
  AlertTriangle, 
  Sparkles, 
  Check, 
  Edit3,
  RefreshCw,
  Trash2,
  Bot
} from 'lucide-react';
import { Obra } from '@/lib/types';
import { api } from '@/lib/api';

interface HeaderProps {
  obras: Obra[];
  obraActiva: Obra | null;
  onSelectObra: (obra: Obra) => void;
  onRefreshData: () => void;
  onOpenVoiceModal: () => void;
  onOpenInvoiceModal: () => void;
  onOpenIncidentModal: () => void;
  onOpenMcpAgentModal?: () => void;
}

export default function Header({
  obras,
  obraActiva,
  onSelectObra,
  onRefreshData,
  onOpenVoiceModal,
  onOpenInvoiceModal,
  onOpenIncidentModal,
  onOpenMcpAgentModal
}: HeaderProps) {
  const [editingTasa, setEditingTasa] = useState(false);
  const [tasaInput, setTasaInput] = useState(obraActiva?.tasa_bcv ? obraActiva.tasa_bcv.toString() : '918.77');
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [loadingReset, setLoadingReset] = useState(false);
  const [syncingBcv, setSyncingBcv] = useState(false);

  const handleSyncBcv = async () => {
    if (!obraActiva) return;
    setSyncingBcv(true);
    try {
      await api.syncBcvRate(obraActiva.id);
      onRefreshData();
    } catch (e) {
      console.error(e);
    } finally {
      setSyncingBcv(false);
    }
  };

  const handleSaveTasa = async () => {
    if (!obraActiva) return;
    const newTasa = parseFloat(tasaInput);
    if (isNaN(newTasa) || newTasa <= 0) return;

    try {
      await api.updateObra(obraActiva.id, { tasa_bcv: newTasa });
      setEditingTasa(false);
      onRefreshData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCargarDemo = async () => {
    setLoadingDemo(true);
    try {
      await api.seedDemo();
      onRefreshData();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleResetData = async () => {
    if (!window.confirm("¿Deseas vaciar todas las partidas, compras y facturas para empezar en blanco desde cero?")) {
      return;
    }
    setLoadingReset(true);
    try {
      await api.resetData();
      onRefreshData();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingReset(false);
    }
  };

  return (
    <header className="h-16 border-b border-zinc-800 bg-[#090d16]/90 backdrop-blur sticky top-0 z-30 px-6 flex items-center justify-between">
      {/* Selector de Obra */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-orange-500" />
          <select 
            value={obraActiva?.id || ''}
            onChange={(e) => {
              const selected = obras.find(o => o.id === e.target.value);
              if (selected) onSelectObra(selected);
            }}
            className="bg-zinc-900 border border-zinc-700 text-white font-semibold text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-orange-500 max-w-xs truncate"
          >
            {obras.map((o) => (
              <option key={o.id} value={o.id}>
                {o.nombre} ({o.cliente})
              </option>
            ))}
          </select>
        </div>

        {/* Pill de Tasa BCV Editable */}
        <div className="flex items-center gap-2 bg-zinc-900/90 border border-zinc-800 px-3 py-1.5 rounded-lg">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-medium text-zinc-400">Tasa BCV:</span>
          {editingTasa ? (
            <div className="flex items-center gap-1.5">
              <input 
                type="number"
                step="0.01"
                value={tasaInput}
                onChange={(e) => setTasaInput(e.target.value)}
                className="w-20 bg-zinc-800 border border-zinc-600 rounded px-1.5 py-0.5 text-xs text-white font-mono focus:outline-none"
                autoFocus
              />
              <button 
                onClick={handleSaveTasa}
                className="p-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white"
                title="Guardar Tasa"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-white">
                {obraActiva?.tasa_bcv ? `${obraActiva.tasa_bcv.toFixed(2)} Bs/$` : '918.77 Bs/$'}
              </span>
              <button 
                onClick={() => {
                  setTasaInput(obraActiva?.tasa_bcv?.toString() || '918.77');
                  setEditingTasa(true);
                }}
                className="text-zinc-500 hover:text-zinc-300 p-0.5 rounded transition"
                title="Editar Tasa BCV manualmente"
              >
                <Edit3 className="w-3 h-3" />
              </button>
              <button
                onClick={handleSyncBcv}
                disabled={syncingBcv || !obraActiva}
                className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 hover:bg-emerald-900/80 border border-emerald-800/60 px-2 py-0.5 rounded transition disabled:opacity-50"
                title="Sincronizar con la Tasa Oficial del BCV en vivo"
              >
                <RefreshCw className={`w-3 h-3 ${syncingBcv ? 'animate-spin' : ''}`} />
                <span>Oficial BCV</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Botones de Acción Rápida (Respaldo Web Total) */}
      <div className="flex items-center gap-2.5">
        {/* Botón Discreto Cargar Obra Demo */}
        <button
          onClick={handleCargarDemo}
          disabled={loadingDemo}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800/80 text-zinc-300 hover:text-white hover:bg-zinc-700 transition"
          title="Carga una obra completa con partidas, gastos e incidencias para pruebas"
        >
          {loadingDemo ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-amber-400" />}
          <span>Cargar Demo</span>
        </button>

        {/* Botón Limpiar Todo */}
        <button
          onClick={handleResetData}
          disabled={loadingReset}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-red-900/40 bg-zinc-900/90 text-zinc-400 hover:text-red-400 hover:border-red-700/60 transition"
          title="Borrar todas las partidas y comenzar un proyecto limpio en blanco ($0.00)"
        >
          {loadingReset ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5 text-red-400" />}
          <span>Limpiar Todo</span>
        </button>

        {/* Botón Agente IA MCP + Gemini */}
        {onOpenMcpAgentModal && (
          <button
            onClick={onOpenMcpAgentModal}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-purple-500/50 bg-purple-950/40 hover:bg-purple-900/60 text-purple-200 transition shadow-sm hover:shadow-purple-500/20 shadow-purple-950/50"
            title="Abrir Asistente IA conectado a Gemini 2.5 Flash y Servidor MCP"
          >
            <Bot className="w-4 h-4 text-purple-400 animate-pulse" />
            <span>Agente IA (MCP)</span>
          </button>
        )}

        {/* Cuantificar por Voz / Micrófono */}
        <button
          onClick={onOpenVoiceModal}
          className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-500 text-white transition shadow-sm"
        >
          <Mic className="w-4 h-4" />
          <span>Voz / Cuantificar</span>
        </button>

        {/* Subir Factura */}
        <button
          onClick={onOpenInvoiceModal}
          className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
        >
          <Upload className="w-4 h-4 text-emerald-400" />
          <span>Subir Factura</span>
        </button>

        {/* Reportar Parada / Daño */}
        <button
          onClick={onOpenIncidentModal}
          className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border border-red-900/50 bg-red-950/20 hover:bg-red-950/40 text-red-300 transition"
        >
          <AlertTriangle className="w-4 h-4 text-red-400" />
          <span>Parada / Daño</span>
        </button>
      </div>
    </header>
  );
}
