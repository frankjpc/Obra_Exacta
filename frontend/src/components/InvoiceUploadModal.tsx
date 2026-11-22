'use client';

import React, { useState } from 'react';
import { Upload, X, AlertOctagon, CheckCircle2, ShieldCheck, Loader2, FileImage } from 'lucide-react';
import { api } from '@/lib/api';

interface InvoiceUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  obraId: string;
  onSuccess: () => void;
}

export default function InvoiceUploadModal({
  isOpen,
  onClose,
  obraId,
  onSuccess
}: InvoiceUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [auditResult, setAuditResult] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setAuditResult(null);
      setErrorMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const res = await api.uploadFactura(obraId, file);
      setAuditResult(res);
      setTimeout(() => {
        onSuccess();
      }, 1500);
    } catch (e: any) {
      setErrorMessage(e.message || 'Error al procesar la factura');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-zinc-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-emerald-600/20 text-emerald-400">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Carga de Factura de Ferretería</h3>
              <p className="text-xs text-zinc-400">Optimización Pillow, anti-duplicados SHA-256 y auditoría</p>
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
          {!previewUrl ? (
            <label className="border-2 border-dashed border-zinc-700 hover:border-orange-500 rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition bg-zinc-900/50 hover:bg-zinc-900">
              <FileImage className="w-12 h-12 text-zinc-500 mb-3" />
              <span className="text-sm font-semibold text-white">Haz clic para seleccionar la foto de la factura</span>
              <span className="text-xs text-zinc-500 mt-1">Soporta JPG, PNG, WEBP de ferretería o materiales</span>
              <input 
                type="file" 
                accept="image/*" 
                className="hidden" 
                onChange={handleFileChange} 
              />
            </label>
          ) : (
            <div className="space-y-4">
              <div className="relative rounded-xl overflow-hidden border border-zinc-700 bg-black max-h-56 flex items-center justify-center">
                <img src={previewUrl} alt="Factura Preview" className="max-h-56 object-contain" />
                <button
                  onClick={() => {
                    setFile(null);
                    setPreviewUrl(null);
                    setAuditResult(null);
                  }}
                  className="absolute top-2 right-2 p-1 rounded-full bg-black/70 text-white hover:bg-black"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {!auditResult && (
                <button
                  onClick={handleUpload}
                  disabled={isUploading}
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg transition"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Auditando con Pillow, SHA-256 y Gemini...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-4 h-4" />
                      <span>Auditar y Cargar a la Obra</span>
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Audit Result Display */}
          {auditResult && (
            <div className="mt-4 space-y-3">
              {auditResult.alerta_roja ? (
                <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-700 text-red-200">
                  <div className="flex items-center gap-2 font-bold text-sm text-red-400">
                    <AlertOctagon className="w-5 h-5 shrink-0" />
                    <span>ALERTA ROJA EN AUDITORÍA</span>
                  </div>
                  <p className="text-xs mt-1.5 leading-relaxed">{auditResult.detalle_alerta}</p>
                </div>
              ) : (
                <div className="p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-700 text-emerald-200">
                  <div className="flex items-center gap-2 font-bold text-sm text-emerald-400">
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <span>Factura Aprobada y Conformada</span>
                  </div>
                  <p className="text-xs mt-1">Margen restante de la obra: {auditResult.margen_restante_pct}% (${auditResult.margen_restante_usd ? auditResult.margen_restante_usd.toFixed(2) : '0.00'})</p>
                </div>
              )}

              {auditResult.factura && (
                <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Proveedor:</span>
                    <span className="font-semibold text-white">{auditResult.factura.proveedor}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Total Facturado:</span>
                    <span className="font-mono font-bold text-emerald-400">
                      ${auditResult.factura.total_usd?.toFixed(2)} | Bs. {auditResult.factura.total_bs?.toLocaleString()}
                    </span>
                  </div>
                  {auditResult.factura.hash_sha256 && (
                    <div className="flex justify-between text-[10px] pt-1 border-t border-zinc-800">
                      <span className="text-zinc-500">Hash SHA-256:</span>
                      <span className="font-mono text-zinc-400 truncate max-w-xs">{auditResult.factura.hash_sha256.slice(0, 16)}...</span>
                    </div>
                  )}
                </div>
              )}
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
