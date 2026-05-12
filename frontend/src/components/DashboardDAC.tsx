import React, { useState, useEffect, useRef } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { BarChart2, Bot, Send, RefreshCw, Upload, AlertTriangle } from 'lucide-react';

const API = (path: string) => `http://localhost:8000${path}`;

interface DashboardRow {
  municipio: string;
  ano: number;
  total_escolas: number;
  total_matriculas: number;
  aprovados: number;
  reprovados: number;
  abandono: number;
  transferidos: number;
  taxa_aprovacao: number;
  taxa_abandono: number;
  taxa_reprovacao: number;
}

interface ChatMsg {
  role: 'user' | 'ai';
  content: string;
}

interface StatusDB {
  total_escolas: number;
  total_registros: number;
  anos_disponiveis: number[];
  importado: boolean;
}

const CORES = {
  aprovacao: '#22c55e',
  abandono: '#ef4444',
  reprovacao: '#f59e0b',
  matriculas: '#3b82f6',
};

export const DashboardDAC: React.FC = () => {
  const [municipios, setMunicipios] = useState<string[]>([]);
  const [anos, setAnos] = useState<number[]>([]);
  const [municipioSel, setMunicipioSel] = useState('');
  const [anoSel, setAnoSel] = useState('');
  const [dados, setDados] = useState<DashboardRow[]>([]);
  const [evolucao, setEvolucao] = useState<DashboardRow[]>([]);
  const [status, setStatus] = useState<StatusDB | null>(null);
  const [loading, setLoading] = useState(false);
  const [importando, setImportando] = useState(false);
  const [importMsg, setImportMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [streamingAI, setStreamingAI] = useState('');
  const chatRef = useRef<HTMLDivElement>(null);
  const token = localStorage.getItem('nexus_token');

  const headers = { Authorization: `Bearer ${token}` };

  // Carrega status e listas ao montar
  useEffect(() => {
    fetchStatus();
    fetchMunicipios();
    fetchAnos();
    fetchEvolucao();
  }, []);

  // Recarrega dados do dashboard quando filtros mudam
  useEffect(() => {
    fetchDashboard();
  }, [municipioSel, anoSel]);

  // Auto-scroll chat
  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' });
  }, [msgs, streamingAI]);

  async function fetchStatus() {
    const res = await fetch(API('/dac/status'));
    if (res.ok) setStatus(await res.json());
  }

  async function fetchMunicipios() {
    const res = await fetch(API('/dac/municipios'));
    if (res.ok) setMunicipios(await res.json());
  }

  async function fetchAnos() {
    const res = await fetch(API('/dac/anos'));
    if (res.ok) setAnos(await res.json());
  }

  async function fetchEvolucao() {
    const res = await fetch(API('/dac/evolucao-estado'));
    if (res.ok) setEvolucao(await res.json());
  }

  async function fetchDashboard() {
    setLoading(true);
    const params = new URLSearchParams();
    if (municipioSel) params.set('municipio', municipioSel);
    if (anoSel) params.set('ano', anoSel);
    const res = await fetch(API(`/dac/dashboard?${params}`));
    if (res.ok) setDados(await res.json());
    setLoading(false);
  }

  async function onFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    setImportando(true);
    setImportMsg(`Enviando ${file.name}…`);

    const form = new FormData();
    form.append('file', file);

    try {
      const res = await fetch(API('/dac/importar'), {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const json = await res.json();
      if (json.erro) {
        setImportMsg(`Erro: ${json.erro}`);
      } else {
        setImportMsg(`✓ ${file.name} — ${json.registros_inseridos} inseridos, ${json.escolas_novas} escolas novas`);
        fetchStatus();
        fetchMunicipios();
        fetchAnos();
        fetchEvolucao();
        fetchDashboard();
      }
    } catch (err) {
      setImportMsg('Erro de conexão com o backend.');
    } finally {
      setImportando(false);
    }
  }

  async function enviarChat() {
    const msg = input.trim();
    if (!msg) return;
    setInput('');
    setMsgs(prev => [...prev, { role: 'user', content: msg }]);
    setStreamingAI('');

    const body = {
      message: msg,
      municipio: municipioSel || undefined,
      ano: anoSel ? parseInt(anoSel) : undefined,
    };

    const res = await fetch(API('/dac/chat'), {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulated = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      const lines = text.split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const json = JSON.parse(line.slice(6));
          if (json.type === 'chunk') {
            accumulated += json.content;
            setStreamingAI(accumulated);
          } else if (json.type === 'complete') {
            setMsgs(prev => [...prev, { role: 'ai', content: accumulated }]);
            setStreamingAI('');
          }
        } catch {}
      }
    }
  }

  // Dados para gráficos
  const dadosEvolucao = municipioSel ? dados : evolucao;

  const dadosPizza = dados.length > 0
    ? (() => {
        const last = dados[dados.length - 1];
        return [
          { name: 'Aprovados', value: last.aprovados, fill: CORES.aprovacao },
          { name: 'Reprovados', value: last.reprovados, fill: CORES.reprovacao },
          { name: 'Abandono', value: last.abandono, fill: CORES.abandono },
        ];
      })()
    : [];

  const indicadoresUltimo = dados.length > 0 ? dados[dados.length - 1] : null;

  return (
    <div className="flex h-full bg-[#020617] text-white overflow-hidden">
      {/* ── Painel Principal ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <BarChart2 className="w-6 h-6 text-blue-400" />
            <div>
              <h1 className="font-bold text-lg">Dashboard Educação MS</h1>
              <p className="text-xs text-slate-400">ODS 4 — Rede Pública 2018–2026</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {status && (
              <span className="text-xs text-slate-500">
                {status.importado
                  ? `${status.total_escolas.toLocaleString()} escolas · ${status.total_registros.toLocaleString()} registros`
                  : 'Banco vazio'}
              </span>
            )}
            <div className="flex flex-col items-end gap-1">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={onFileSelected}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importando}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-sm transition-colors"
              >
                {importando ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                {importando ? 'Enviando…' : 'Carregar CSV'}
              </button>
              {importMsg && (
                <p className="text-xs text-slate-400 max-w-xs text-right">{importMsg}</p>
              )}
            </div>
          </div>
        </div>

        {/* Filtros */}
        <div className="px-6 py-3 flex gap-4 border-b border-slate-800 bg-slate-900/30">
          <select
            value={municipioSel}
            onChange={e => setMunicipioSel(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white flex-1 max-w-xs"
          >
            <option value="">Todos os municípios</option>
            {municipios.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <select
            value={anoSel}
            onChange={e => setAnoSel(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white"
          >
            <option value="">Todos os anos</option>
            {anos.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">

          {/* KPIs */}
          {indicadoresUltimo && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Matrículas', value: indicadoresUltimo.total_matriculas.toLocaleString(), color: 'text-blue-400' },
                { label: 'Taxa Aprovação', value: `${indicadoresUltimo.taxa_aprovacao}%`, color: 'text-green-400' },
                { label: 'Taxa Abandono', value: `${indicadoresUltimo.taxa_abandono}%`, color: 'text-red-400' },
                { label: 'Taxa Reprovação', value: `${indicadoresUltimo.taxa_reprovacao}%`, color: 'text-yellow-400' },
              ].map(k => (
                <div key={k.label} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">{k.label}</p>
                  <p className={`text-2xl font-bold ${k.color}`}>{k.value}</p>
                </div>
              ))}
            </div>
          )}

          {!status?.importado && (
            <div className="flex items-center gap-3 bg-yellow-950/40 border border-yellow-800/50 rounded-xl p-4 text-yellow-300 text-sm">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              Banco vazio. Clique em "Importar CSVs" para carregar os dados da pasta Dados/.
            </div>
          )}

          {loading && (
            <div className="text-center text-slate-500 py-8">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
              Carregando dados…
            </div>
          )}

          {/* Gráfico: Evolução de Matrículas */}
          {dadosEvolucao.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                Evolução de Matrículas {municipioSel ? `— ${municipioSel}` : '— Estado'}
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={dadosEvolucao}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="ano" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="total_matriculas" name="Matrículas" stroke={CORES.matriculas} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Gráfico: Taxas */}
          {dadosEvolucao.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">
                Taxas Históricas (%) {municipioSel ? `— ${municipioSel}` : '— Estado'}
              </h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={dadosEvolucao}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="ano" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis unit="%" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                    formatter={(v: number) => `${v}%`}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="taxa_aprovacao" name="Aprovação" stroke={CORES.aprovacao} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="taxa_abandono" name="Abandono" stroke={CORES.abandono} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="taxa_reprovacao" name="Reprovação" stroke={CORES.reprovacao} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Gráfico: Comparativo por ano */}
          {dados.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Aprovados / Reprovados / Abandono por Ano</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={dados}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="ano" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="aprovados" name="Aprovados" fill={CORES.aprovacao} radius={[3, 3, 0, 0]} />
                  <Bar dataKey="reprovados" name="Reprovados" fill={CORES.reprovacao} radius={[3, 3, 0, 0]} />
                  <Bar dataKey="abandono" name="Abandono" fill={CORES.abandono} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* ── Chat Analítico ── */}
      <div className="w-96 flex flex-col border-l border-slate-800 bg-slate-900/40">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
          <Bot className="w-5 h-5 text-blue-400" />
          <div>
            <p className="text-sm font-semibold">Analista IA</p>
            <p className="text-xs text-slate-500">
              Interpreta os dados {municipioSel ? `de ${municipioSel}` : 'do estado'}{anoSel ? ` em ${anoSel}` : ''}
            </p>
          </div>
        </div>

        <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.length === 0 && !streamingAI && (
            <div className="text-center text-slate-600 text-sm mt-8 space-y-2">
              <Bot className="w-10 h-10 mx-auto text-slate-700" />
              <p>Pergunte sobre os dados educacionais.</p>
              <p className="text-xs">Ex: "Quais municípios têm maior abandono?" ou "O que explica a queda de matrículas?"</p>
            </div>
          )}

          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-blue-700 text-white'
                    : 'bg-slate-800 text-slate-200'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {streamingAI && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-xl px-3 py-2 text-sm bg-slate-800 text-slate-200 leading-relaxed">
                {streamingAI}
                <span className="inline-block w-1.5 h-4 bg-blue-400 ml-1 animate-pulse align-middle" />
              </div>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-slate-800">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && enviarChat()}
              placeholder="Pergunte sobre os dados…"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-600"
            />
            <button
              onClick={enviarChat}
              disabled={!input.trim()}
              className="p-2 rounded-lg bg-blue-700 hover:bg-blue-600 disabled:opacity-40 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
