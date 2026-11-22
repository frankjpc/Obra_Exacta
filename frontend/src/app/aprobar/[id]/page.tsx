'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { 
  AlertTriangle, 
  CheckCircle2, 
  DollarSign, 
  HardHat, 
  Building2, 
  ShieldCheck, 
  Send,
  Loader2,
  Calendar,
  Lock
} from 'lucide-react';
import { api } from '@/lib/api';
import { LibroObraItem, Obra } from '@/lib/types';

export default function AprobarIncidenciaPage() {
  const params = useParams();
  const token = params.id as string;

  const [loading, setLoading] = useState(true);
  const [incidencia, setIncidencia] = useState<LibroObraItem | null>(null);
  const [obra, setObra] = useState<Obra | null>(null);
  const [clienteNombre, setClienteNombre] = useState('');
  const [isApproving, setIsApproving] = useState(false);
  const [approvedSuccess, setApprovedSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;

    api.getIncidenciaParaAprobar(token)
      .then((data) => {
        setIncidencia(data.incidencia);
        setObra(data.obra);
        if (data.incidencia?.cliente_nombre) {
          setClienteNombre(data.incidencia.cliente_nombre);
        }
        if (data.incidencia?.estado_aprobacion === 'aprobado') {
          setApprovedSuccess(true);
        }
      })
      .catch((err) => {
        console.error(err);
        setErrorMessage('La solicitud no fue encontrada o ya expiró.');
      })
      .finally(() => setLoading(false));
  }, [token]);

  const handleAprobar = async () => {
    if (!token) return;
    setIsApproving(true);
    setErrorMessage(null);

    try {
      await api.aprobarIncidencia(token, clienteNombre || 'Cliente Autorizado');
      setApprovedSuccess(true);
    } catch (e: any) {
      setErrorMessage(e.message || 'Error al aprobar el adicional');
    } finally {
      setIsApproving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#070b12] text-white flex flex-col items-center justify-center p-4">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500 mb-3" />
        <p className="text-xs text-zinc-400 font-mono">Cargando detalles de la obra...</p>
      </div>
    );
  }

  if (errorMessage && !incidencia) {
    return (
      <div className="min-h-screen bg-[#070b12] text-white flex flex-col items-center justify-center p-6 text-center">
        <AlertTriangle className="w-12 h-12 text-red-400 mb-3" />
        <h2 className="text-lg font-bold">Solicitud No Disponible</h2>
        <p className="text-xs text-zinc-400 mt-1 max-w-sm">{errorMessage}</p>
      </div>
    );
  }

  const tasaBcv = obra?.tasa_bcv || 68.50;
  const costoUsd = incidencia?.costo_adicional_usd || 0;
  const costoBs = incidencia?.costo_adicional_bs || costoUsd * tasaBcv;

  return (
    <div className="min-h-screen bg-[#070b12] text-zinc-100 flex justify-center py-6 px-4 sm:px-6">
      <div className="w-full max-w-md space-y-5">
        {/* Brand Header */}
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-orange-600 flex items-center justify-center text-white shadow-lg shadow-orange-600/30">
              <HardHat className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-white text-base tracking-tight">ObraExacta</span>
              <p className="text-[10px] text-zinc-400 font-medium">Firma Digital de Partida Adicional</p>
            </div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono flex items-center gap-1 border border-zinc-700">
            <Lock className="w-3 h-3 text-emerald-400" /> Token Seguro
          </span>
        </div>

        {/* Obra & Cliente Banner */}
        <div className="p-4 rounded-2xl bg-zinc-900/90 border border-zinc-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-orange-400 flex items-center gap-1 mb-1">
            <Building2 className="w-3.5 h-3.5" /> Proyecto
          </span>
          <h2 className="text-sm font-bold text-white">{obra?.nombre || 'Obra en Ejecución'}</h2>
          <p className="text-xs text-zinc-400 mt-0.5">{obra?.cliente || 'Cliente'}</p>
        </div>

        {/* FOTO DEL DAÑO OCULTO */}
        {incidencia?.foto_url && (
          <div className="rounded-2xl overflow-hidden border border-zinc-800 bg-black shadow-xl">
            <div className="relative max-h-64 overflow-hidden">
              <img 
                src={incidencia.foto_url} 
                alt="Foto del Daño Oculto" 
                className="w-full h-56 object-cover"
              />
              <div className="absolute top-3 left-3 bg-red-600/90 backdrop-blur px-2.5 py-1 rounded-lg text-white font-bold text-[10px] flex items-center gap-1.5 shadow-lg">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>EVIDENCIA EN CAMPO</span>
              </div>
            </div>
          </div>
        )}

        {/* FICHA TÉCNICA DEL DAÑO */}
        <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
              Parada Técnica Registrada
            </span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 font-bold">
              +{incidencia?.porcentaje_variacion}% del contrato
            </span>
          </div>

          <h3 className="text-lg font-black text-white leading-snug">
            {incidencia?.titulo}
          </h3>

          <p className="text-xs text-zinc-300 leading-relaxed bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-800">
            {incidencia?.descripcion}
          </p>

          <div className="text-[11px] text-zinc-500 flex items-center gap-1.5 pt-1">
            <Calendar className="w-3.5 h-3.5" />
            <span>Reportado: {incidencia?.created_at ? new Date(incidencia.created_at).toLocaleString() : 'Hoy'}</span>
          </div>
        </div>

        {/* COSTO ADICIONAL BIMONETARIO */}
        <div className="p-5 rounded-2xl border border-emerald-900/60 bg-gradient-to-br from-emerald-950/30 to-zinc-900 shadow-xl space-y-2">
          <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">
            Presupuesto Adicional Requerido
          </span>

          <div className="flex items-baseline justify-between pt-1">
            <div>
              <span className="text-3xl font-black text-white font-mono">
                ${costoUsd.toFixed(2)}
              </span>
              <span className="text-xs text-zinc-400 ml-1">USD</span>
            </div>

            <div className="text-right">
              <span className="text-base font-bold text-emerald-400 font-mono">
                Bs. {costoBs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono block">Tasa BCV {tasaBcv.toFixed(2)} Bs/$</span>
            </div>
          </div>
        </div>

        {/* ACCIÓN DE APROBACIÓN */}
        {approvedSuccess ? (
          <div className="p-6 rounded-2xl bg-emerald-950/60 border border-emerald-700 text-center space-y-3 shadow-2xl animate-fade-in">
            <div className="w-14 h-14 rounded-full bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h4 className="text-base font-extrabold text-white">¡Adicional Aprobado con Éxito!</h4>
            <p className="text-xs text-emerald-200">
              Se ha confirmado la partida y enviado notificación automática al contratista por Telegram para reanudar trabajos.
            </p>
            <div className="pt-2 text-[10px] text-zinc-400 font-mono">
              Firma digital registrada: {clienteNombre || 'Cliente Autorizado'}
            </div>
          </div>
        ) : (
          <div className="space-y-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                Nombre de quien autoriza:
              </label>
              <input 
                type="text"
                value={clienteNombre}
                onChange={(e) => setClienteNombre(e.target.value)}
                placeholder="Nombre y apellido o cargo"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <button
              onClick={handleAprobar}
              disabled={isApproving}
              className="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-sm rounded-xl flex items-center justify-center gap-2 shadow-xl shadow-emerald-600/30 transition active:scale-95"
            >
              {isApproving ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Registrando firma y notificando...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-5 h-5" />
                  <span>Aprobar Adicional de Obra</span>
                </>
              )}
            </button>

            <p className="text-[11px] text-zinc-500 text-center leading-relaxed">
              Al presionar "Aprobar Adicional", se notificará instantáneamente al ingeniero residente para continuar con los trabajos de obra.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
