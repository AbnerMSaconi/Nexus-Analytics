import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Server, RefreshCw, CheckCircle, XCircle, Thermometer } from 'lucide-react';

import { API_BASE as _API_BASE } from '../utils/apiBase';
const API_BASE = () => _API_BASE;

interface GpuInfo {
  index: number;
  name: string;
  utilizacao_pct: number;
  memoria_usada_mb: number;
  memoria_total_mb: number;
  temperatura_c: number;
}

interface StatusData {
  llm: { ok: boolean; model: string | null; n_ctx: number | null; slots: { total: number; processando: number } | null };
  embedding: { ok: boolean; model: string | null };
  gpu: GpuInfo[];
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1">
      <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export const SystemStatus: React.FC = () => {
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function fetch_status() {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE()}/system/status`);
      if (r.ok) {
        setData(await r.json());
        setLastUpdate(new Date());
      }
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    fetch_status();
    const interval = setInterval(fetch_status, 8000);
    return () => clearInterval(interval);
  }, []);

  const modelName = (path: string | null) => {
    if (!path) return '—';
    return path.split('/').pop() ?? path;
  };

  return (
    <div className="p-4 space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-300 flex items-center gap-2">
          <Server className="w-4 h-4 text-blue-400" />
          Status do Sistema
        </h2>
        <button
          onClick={fetch_status}
          className="text-slate-500 hover:text-slate-300 transition-colors"
          title="Atualizar"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {!data && !loading && (
        <p className="text-slate-600 text-xs">Sem dados. Backend offline?</p>
      )}

      {data && (
        <>
          {/* LLM */}
          <div className="bg-slate-800/60 rounded-xl p-3 space-y-2 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" /> LLM
              </span>
              {data.llm.ok
                ? <CheckCircle className="w-4 h-4 text-green-400" />
                : <XCircle className="w-4 h-4 text-red-400" />}
            </div>
            <p className="text-white font-mono text-xs truncate" title={data.llm.model ?? ''}>
              {modelName(data.llm.model)}
            </p>
            {data.llm.n_ctx && (
              <p className="text-slate-500 text-xs">Contexto: {data.llm.n_ctx.toLocaleString()} tokens</p>
            )}
            {data.llm.slots && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-500">Slots:</span>
                <span className={data.llm.slots.processando > 0 ? 'text-yellow-400 font-semibold' : 'text-slate-400'}>
                  {data.llm.slots.processando}/{data.llm.slots.total} ativos
                </span>
                {data.llm.slots.processando > 0 && (
                  <span className="flex items-center gap-1 text-yellow-400">
                    <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse" />
                    processando
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Embedding */}
          <div className="bg-slate-800/60 rounded-xl p-3 space-y-2 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" /> Embedding
              </span>
              {data.embedding.ok
                ? <CheckCircle className="w-4 h-4 text-green-400" />
                : <XCircle className="w-4 h-4 text-red-400" />}
            </div>
            <p className="text-white font-mono text-xs truncate" title={data.embedding.model ?? ''}>
              {modelName(data.embedding.model)}
            </p>
          </div>

          {/* GPU */}
          {data.gpu.length > 0 ? (
            data.gpu.map(gpu => (
              <div key={gpu.index} className="bg-slate-800/60 rounded-xl p-3 space-y-2 border border-slate-700/50">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 text-xs">GPU {gpu.index}</span>
                  <span className="flex items-center gap-1 text-slate-400 text-xs">
                    <Thermometer className="w-3 h-3" />
                    {gpu.temperatura_c}°C
                  </span>
                </div>
                <p className="text-white text-xs font-medium">{gpu.name}</p>

                <div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>Utilização</span>
                    <span className={gpu.utilizacao_pct > 80 ? 'text-orange-400' : 'text-slate-400'}>
                      {gpu.utilizacao_pct}%
                    </span>
                  </div>
                  <Bar value={gpu.utilizacao_pct} max={100} color={gpu.utilizacao_pct > 80 ? 'bg-orange-400' : 'bg-blue-500'} />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>VRAM</span>
                    <span>{(gpu.memoria_usada_mb / 1024).toFixed(1)} / {(gpu.memoria_total_mb / 1024).toFixed(1)} GB</span>
                  </div>
                  <Bar value={gpu.memoria_usada_mb} max={gpu.memoria_total_mb} color="bg-purple-500" />
                </div>
              </div>
            ))
          ) : (
            <div className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/50 text-xs text-slate-500">
              nvidia-smi não disponível no container.
            </div>
          )}

          {lastUpdate && (
            <p className="text-slate-700 text-xs text-right">
              Atualizado: {lastUpdate.toLocaleTimeString()}
            </p>
          )}
        </>
      )}
    </div>
  );
};
