'use client';

import React, { useState } from 'react';
import { AlertTriangle, X, Link as LinkIcon, Check, Loader2, DollarSign, Camera } from 'lucide-react';
import { api } from '@/lib/api';

interface IncidentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  obraId: string;
  presupuestoBaseUsd: number;
  onSuccess: () => void;
}

export default function IncidentUploadModal({
  isOpen,
  onClose,
  obraId,
  presupuestoBaseUsd,
  onSuccess
}: IncidentUploadModalProps) {
  const [titulo, setTitulo] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [costoUsd, setCostoUsd] = useState('250.00');
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const numCosto = parseFloat(costoUsd) || 0;
  const pctVariacion = presupuestoBaseUsd > 0 ? ((numCosto / presupuestoBaseUsd) * 100).toFixed(2) : '5.00';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo || !descripcion) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append('obra_id', obraId);
      formData.append('titulo', titulo);
      formData.append('descripcion', descripcion);
      formData.append('costo_adicional_usd', numCosto.toString());
      if (file) {
        formData.append('foto', file);
      }

      const res = await api.reportarIncidencia(formData);
      const link = `${window.location.origin}/aprobar/${res.token_aprobacion || res.incidencia?.token_aprobacion}`;
      setGeneratedLink(link);
      onSuccess();
    } catch (err: any) {
      setErrorMessage(err.message || 'Error al reportar la parada');
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyToClipboard = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-zinc-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-red-600/20 text-red-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Registrar Parada por Daño Oculto</h3>
              <p className="text-xs text-zinc-400">Calcula % de variación y genera enlace móvil de aprobación</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {!generatedLink ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Título de la Parada / Daño:
                </label>
                <input
                  type="text"
                  required
                  value={titulo}
                  onChange={(e) => setTitulo(e.target.value)}
                  placeholder="Ej. Tubería de aguas servidas rota oculta tras tabique"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Descripción Técnica y Motivo de Paralización:
                </label>
                <textarea
                  required
                  rows={3}
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                  placeholder="Detalla el hallazgo, por qué se debe detener la obra y la solución propuesta..."
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Costo Adicional Estimado ($):
                  </label>
                  <div className="relative">
                    <DollarSign className="w-4 h-4 text-zinc-400 absolute left-3 top-3" />
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={costoUsd}
                      onChange={(e) => setCostoUsd(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-xl pl-9 pr-3 py-2 text-sm text-white font-mono focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Variación Contrato:
                  </label>
                  <div className="h-10 bg-zinc-900/80 border border-zinc-700 rounded-xl px-3 flex items-center font-mono font-bold text-amber-400 text-sm">
                    +{pctVariacion}%
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Foto de Evidencia del Daño (opcional):
                </label>
                <div className="flex items-center gap-2">
                  <label className="flex-1 border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-300 cursor-pointer flex items-center gap-2">
                    <Camera className="w-4 h-4 text-zinc-400" />
                    <span className="truncate">{file ? file.name : 'Tomar o subir foto de la avería'}</span>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => e.target.files && setFile(e.target.files[0])}
                    />
                  </label>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 bg-red-600 hover:bg-red-500 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg transition mt-4"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Registrando en Libro de Obra...</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-4 h-4" />
                    <span>Registrar y Generar Enlace Móvil</span>
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className="text-center py-4 space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-600/20 text-emerald-400 mx-auto flex items-center justify-center">
                <Check className="w-6 h-6" />
              </div>
              <h4 className="font-bold text-white text-base">Enlace de Aprobación Generado</h4>
              <p className="text-xs text-zinc-400">
                Reenvía este enlace directo por WhatsApp o Telegram al cliente para que revise y apruebe en 1 toque:
              </p>

              <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-700 rounded-xl p-2.5">
                <input
                  type="text"
                  readOnly
                  value={generatedLink}
                  className="bg-transparent text-xs text-zinc-300 flex-1 outline-none truncate font-mono"
                />
                <button
                  onClick={copyToClipboard}
                  className="px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs flex items-center gap-1.5 transition"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <LinkIcon className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copiado' : 'Copiar'}</span>
                </button>
              </div>

              <div className="pt-2">
                <button
                  onClick={onClose}
                  className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold text-xs rounded-xl"
                >
                  Cerrar
                </button>
              </div>
            </div>
          )}

          {errorMessage && (
            <div className="mt-4 p-3 rounded-xl bg-red-950/40 border border-red-800 text-xs text-red-300">
              {errorMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
