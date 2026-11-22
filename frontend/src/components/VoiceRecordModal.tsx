'use client';

import React, { useState, useRef } from 'react';
import { Mic, Square, Send, X, Sparkles, Loader2, Volume2, FileText } from 'lucide-react';
import { api } from '@/lib/api';

interface VoiceRecordModalProps {
  isOpen: boolean;
  onClose: () => void;
  obraId: string;
  tasaBcv: number;
  onSuccess: () => void;
}

export default function VoiceRecordModal({
  isOpen,
  onClose,
  obraId,
  tasaBcv,
  onSuccess
}: VoiceRecordModalProps) {
  const [activeTab, setActiveTab] = useState<'mic' | 'text'>('mic');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [textInput, setTextInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultSummary, setResultSummary] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  if (!isOpen) return null;

  const startRecording = async () => {
    try {
      setErrorMessage(null);
      setResultSummary(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/ogg; codecs=opus' });
        setAudioBlob(blob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error(err);
      setErrorMessage('No se pudo acceder al micrófono del navegador. Puedes usar la pestaña de texto para escribir el levantamiento.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleSendAudio = async () => {
    if (!audioBlob) return;
    setIsProcessing(true);
    setErrorMessage(null);
    try {
      const res = await api.procesarLevantamientoAudio(obraId, audioBlob);
      setResultSummary(`Presupuesto cubicado con éxito: ${res.presupuesto.partidas.length} partidas generadas.`);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (e: any) {
      setErrorMessage(e.message || 'Error al procesar el audio');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendText = async () => {
    if (!textInput.trim()) return;
    setIsProcessing(true);
    setErrorMessage(null);
    try {
      const res = await api.procesarLevantamientoTexto(obraId, textInput, tasaBcv);
      setResultSummary(`Presupuesto cubicado con éxito: ${res.presupuesto.partidas.length} partidas generadas.`);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (e: any) {
      setErrorMessage(e.message || 'Error al procesar el texto');
    } finally {
      setIsProcessing(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0f172a] border border-zinc-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Modal Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-orange-600/20 text-orange-400">
              <Mic className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Cubicación por Voz o Texto (2D)</h3>
              <p className="text-xs text-zinc-400">Gemini 2.5 Flash extrae medidas y el motor calcula materiales</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-zinc-800">
          <button
            onClick={() => setActiveTab('mic')}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition ${
              activeTab === 'mic' 
                ? 'border-orange-500 text-orange-400 bg-orange-500/5' 
                : 'border-transparent text-zinc-400 hover:text-white'
            }`}
          >
            <Volume2 className="w-4 h-4" />
            Micrófono Web
          </button>
          <button
            onClick={() => setActiveTab('text')}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition ${
              activeTab === 'text' 
                ? 'border-orange-500 text-orange-400 bg-orange-500/5' 
                : 'border-transparent text-zinc-400 hover:text-white'
            }`}
          >
            <FileText className="w-4 h-4" />
            Texto Libre de Cuantificación
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {activeTab === 'mic' ? (
            <div className="text-center py-4">
              <div className="flex justify-center mb-4">
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isProcessing}
                  className={`w-24 h-24 rounded-full flex flex-col items-center justify-center text-white font-bold transition-all shadow-xl ${
                    isRecording 
                      ? 'bg-red-600 animate-pulse ring-8 ring-red-600/30' 
                      : 'bg-orange-600 hover:bg-orange-500 ring-4 ring-orange-600/20'
                  }`}
                >
                  {isRecording ? (
                    <>
                      <Square className="w-8 h-8 mb-1" />
                      <span className="text-xs">Detener</span>
                    </>
                  ) : (
                    <>
                      <Mic className="w-8 h-8 mb-1" />
                      <span className="text-xs">Grabar</span>
                    </>
                  )}
                </button>
              </div>

              <div className="font-mono text-lg font-bold text-white mb-2">
                {isRecording ? (
                  <span className="text-red-400 flex items-center justify-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
                    Grabando... {formatTime(recordingSeconds)}
                  </span>
                ) : audioBlob ? (
                  <span className="text-emerald-400">Audio listo ({formatTime(recordingSeconds)})</span>
                ) : (
                  <span className="text-zinc-500 text-xs">Presiona para grabar la nota de voz de obra</span>
                )}
              </div>

              <p className="text-xs text-zinc-400 max-w-sm mx-auto mb-6">
                Ejemplo: "Pared de bloque de 8 metros de largo por 2.80 de alto frisada, 45 m2 de pintura satinada y 16 lámparas panel LED."
              </p>

              {audioBlob && !isRecording && (
                <button
                  onClick={handleSendAudio}
                  disabled={isProcessing}
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg transition"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Cubicando con Gemini y Motor Determinista...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Procesar y Generar Presupuesto</span>
                    </>
                  )}
                </button>
              )}
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-2">
                Describe las partidas y medidas:
              </label>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Ejemplo: Construir pared de bloque de 12 metros de largo por 3 de alto frisada por ambas caras, colocar 60 m2 de porcelanato en piso y montar 18 luminarias LED 60x60..."
                rows={5}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none font-sans"
              />
              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  onClick={() => setTextInput("Pared de bloque de 10 metros de largo por 2.80 de alto frisada a dos caras, 50 m2 de cielo raso en drywall y 15 lámparas panel LED")}
                  className="text-[11px] px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-white border border-zinc-700"
                >
                  Usar plantilla ejemplo
                </button>
              </div>

              <div className="mt-6">
                <button
                  onClick={handleSendText}
                  disabled={isProcessing || !textInput.trim()}
                  className="w-full py-2.5 px-4 bg-orange-600 hover:bg-orange-500 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg transition disabled:opacity-50"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Extrayendo parámetros y calculando...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Calcular Presupuesto 6 Columnas</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Feedback messages */}
          {resultSummary && (
            <div className="mt-4 p-3 rounded-xl bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 shrink-0" />
              <span>{resultSummary}</span>
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
