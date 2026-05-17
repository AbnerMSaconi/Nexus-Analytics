import React, { useState, useEffect, useRef } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  BarChart2, Bot, Send, RefreshCw, Upload, AlertTriangle,
  Database, Trash2,
} from 'lucide-react';

const API = (path: string) => `http://localhost:8000${path}`;

const PALETTE = [
  '#3b82f6', '#22c55e', '#ef4444', '#f59e0b',
  '#a855f7', '#06b6d4', '#f97316', '#ec4899',
];

// Colunas disponíveis para toggle no gráfico
const ALL_COLS = [
  { key: 'total_matriculas',   label: 'Matrículas Total' },
  { key: 'matricula_inicial',  label: 'Matrícula Inicial' },
  { key: 'matricula_apos_censo', label: 'Após Censo' },
  { key: 'aprovados',          label: 'Aprovados' },
  { key: 'reprovados',         label: 'Reprovados' },
  { key: 'abandono',           label: 'Abandono' },
  { key: 'transferidos',       label: 'Transferidos' },
  { key: 'cancelados',         label: 'Cancelados' },
  { key: 'cursando',           label: 'Cursando' },
  { key: 'taxa_aprovacao',     label: 'Aprovação (%)' },
  { key: 'taxa_reprovacao',    label: 'Reprovação (%)' },
  { key: 'taxa_abandono',      label: 'Abandono (%)' },
];

const DEFAULT_COLS = ['total_matriculas', 'aprovados', 'reprovados', 'abandono'];

interface Status {
  total_escolas: number;
  total_registros: number;
  anos_disponiveis: number[];
  importado: boolean;
}

interface DashRow {
  ano: number;
  total_escolas: number;
  total_matriculas: number;
  matricula_inicial: number;
  matricula_apos_censo: number;
  aprovados: number;
  reprovados: number;
  abandono: number;
  transferidos: number;
  cancelados: number;
  cursando: number;
  outras_situacoes: number;
  taxa_aprovacao: number;
  taxa_reprovacao: number;
  taxa_abandono: number;
}

interface ChatMsg { role: 'user' | 'ai'; content: string; }

export const DashboardDAC: React.FC = () => {
  const token    = localStorage.getItem('nexus_token') || '';
  const userRole = JSON.parse(localStorage.getItem('nexus_user') || '{}').role || '';
  const headers  = { Authorization: `Bearer ${token}` };

  const [status, setStatus]           = useState<Status | null>(null);
  const [anos, setAnos]               = useState<number[]>([]);
  const [municipios, setMunicipios]   = useState<string[]>([]);
  const [anoInicio, setAnoInicio]     = useState<string>('');
  const [anoFim, setAnoFim]           = useState<string>('');
  const [municipioSel, setMunicipioSel] = useState('');

  const [dashData, setDashData]             = useState<DashRow[]>([]);
  const [colunasSel, setColunasSel]         = useState<string[]>(DEFAULT_COLS);
  const [loading, setLoading]               = useState(false);

  const [importando, setImportando]         = useState(false);
  const [importMsg, setImportMsg]           = useState('');
  const [mesclarArquivos, setMesclarArquivos] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [msgs, setMsgs]             = useState<ChatMsg[]>([]);
  const [input, setInput]           = useState('');
  const [streamingAI, setStreamingAI] = useState('');
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [msgs, streamingAI]);

  useEffect(() => { fetchDashboard(); }, [anoInicio, anoFim, municipioSel]);

  async function loadAll() {
    await Promise.all([fetchStatus(), fetchAnos(), fetchMunicipios()]);
    fetchDashboard();
  }

  async function fetchStatus() {
    try {
      const res = await fetch(API('/dac/status'));
      if (res.ok) setStatus(await res.json());
    } catch {}
  }

  async function fetchAnos() {
    try {
      const res = await fetch(API('/dac/anos'));
      if (res.ok) setAnos(await res.json());
    } catch {}
  }

  async function fetchMunicipios() {
    try {
      const res = await fetch(API('/dac/municipios'));
      if (res.ok) setMunicipios(await res.json());
    } catch {}
  }

  async function fetchDashboard() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (municipioSel) params.set('municipio', municipioSel);
      if (anoInicio)    params.set('ano_inicio', anoInicio);
      if (anoFim)       params.set('ano_fim', anoFim);
      const res = await fetch(API(`/dac/dashboard?${params}`));
      if (res.ok) setDashData(await res.json());
    } catch {}
    setLoading(false);
  }

  // ── importação base64 ─────────────────────────────────────────────────────
  async function onFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    e.target.value = '';
    setImportando(true);
    setImportMsg(`Lendo ${files.length} arquivo(s)…`);

    const readAsBase64 = (f: File): Promise<{ name: string; content: string }> =>
      new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve({ name: f.name, content: (reader.result as string).split(',')[1] });
        reader.onerror = reject;
        reader.readAsDataURL(f);
      });

    try {
      const fileContents = await Promise.all(files.map(readAsBase64));
      setImportMsg(`Enviando ${files.length} arquivo(s)…`);
      const res = await fetch(API('/dac/importar'), {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: fileContents, mesclar: mesclarArquivos }),
      });
      if (!res.ok) {
        setImportMsg(`Erro ${res.status}: ${(await res.text()).slice(0, 200)}`);
        return;
      }
      const json = await res.json();
      if (json.erro) {
        setImportMsg(`✗ ${json.erro}`);
        return;
      }
      const inseridos = json.registros_inseridos ?? 0;
      const ignorados = json.registros_ignorados ?? 0;
      const novas    = json.escolas_novas ?? 0;
      setImportMsg(`✓ ${inseridos.toLocaleString()} inseridos · ${ignorados.toLocaleString()} ignorados · ${novas.toLocaleString()} escolas novas`);
      await loadAll();
    } catch (err: any) {
      setImportMsg(`Erro de conexão: ${err.message}`);
    } finally {
      setImportando(false);
    }
  }

  // ── deletar ano ───────────────────────────────────────────────────────────
  async function handleDeleteAno(ano: number) {
    if (!window.confirm(`Excluir todos os dados de ${ano}?`)) return;
    try {
      await fetch(API(`/dac/dados/${ano}`), { method: 'DELETE', headers });
      await loadAll();
    } catch {
      alert('Erro ao excluir dados do ano.');
    }
  }

  // ── chat ──────────────────────────────────────────────────────────────────
  async function enviarChat() {
    const msg = input.trim();
    if (!msg) return;
    setInput('');
    setMsgs(prev => [...prev, { role: 'user', content: msg }]);
    setStreamingAI('');

    const res = await fetch(API('/dac/chat'), {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        municipio: municipioSel || null,
        ano_inicio: anoInicio ? parseInt(anoInicio) : null,
        ano_fim:    anoFim    ? parseInt(anoFim)    : null,
      }),
    });
    if (!res.body) return;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulated = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value).split('\n')) {
        if (!line.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === 'chunk') { accumulated += ev.content; setStreamingAI(accumulated); }
          else if (ev.type === 'complete') { setMsgs(p => [...p, { role: 'ai', content: accumulated }]); setStreamingAI(''); }
        } catch {}
      }
    }
  }

  const toggleCol = (col: string) =>
    setColunasSel(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]);

  // ── KPIs da visão atual ───────────────────────────────────────────────────
  const totAp  = dashData.reduce((a, r) => a + r.aprovados, 0);
  const totRep = dashData.reduce((a, r) => a + r.reprovados, 0);
  const totAb  = dashData.reduce((a, r) => a + r.abandono, 0);
  const totMat = dashData.reduce((a, r) => a + r.total_matriculas, 0);
  const baseKpi = totAp + totRep + totAb;
  const kpis = [
    { label: 'Matrículas',        value: totMat.toLocaleString('pt-BR'),   color: PALETTE[0] },
    { label: 'Taxa Aprovação',    value: baseKpi > 0 ? `${(totAp / baseKpi * 100).toFixed(1)}%` : '—', color: PALETTE[1] },
    { label: 'Taxa Reprovação',   value: baseKpi > 0 ? `${(totRep / baseKpi * 100).toFixed(1)}%` : '—', color: PALETTE[2] },
    { label: 'Taxa Abandono',     value: baseKpi > 0 ? `${(totAb / baseKpi * 100).toFixed(1)}%` : '—', color: PALETTE[3] },
  ];

  const filtrosDesc = [
    anoInicio || anoFim ? `Período: ${anoInicio || '...'} → ${anoFim || '...'}` : 'Período: todos',
    municipioSel ? `Local: ${municipioSel}` : 'Local: todos',
  ].join(' · ');

  const temDados = status?.importado ?? false;

  return (
    <div className="flex h-full bg-[#020617] text-white overflow-hidden">

      {/* ── Painel Principal ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-3">
            <BarChart2 className="w-6 h-6 text-blue-400" />
            <div>
              <h1 className="font-bold text-lg">Nexus — Análise de Dados</h1>
              <p className="text-xs text-slate-500">{filtrosDesc}</p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1">
            {status?.importado && (
              <p className="text-xs text-slate-500">
                {status.total_escolas.toLocaleString()} escolas ·{' '}
                {status.total_registros.toLocaleString()} registros ·{' '}
                Anos: {status.anos_disponiveis[0]}–{status.anos_disponiveis[status.anos_disponiveis.length - 1]}
              </p>
            )}
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 cursor-pointer text-xs text-slate-400 select-none">
                <input
                  type="checkbox"
                  checked={mesclarArquivos}
                  onChange={e => setMesclarArquivos(e.target.checked)}
                  className="accent-blue-500 w-3 h-3"
                />
                Mesclar arquivos
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                multiple
                className="hidden"
                onChange={onFileSelected}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importando}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-sm transition-colors"
              >
                {importando ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                {importando ? 'Enviando…' : 'Importar CSV'}
              </button>
            </div>
            {importMsg && <p className="text-xs text-slate-400 max-w-xs text-right">{importMsg}</p>}
          </div>
        </div>

        {/* Filtros */}
        <div className="px-6 py-3 flex flex-wrap gap-3 border-b border-slate-800 bg-slate-900/30 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider">De</span>
            <select
              value={anoInicio}
              onChange={e => setAnoInicio(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="">Início</option>
              {anos.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider">Até</span>
            <select
              value={anoFim}
              onChange={e => setAnoFim(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white"
            >
              <option value="">Fim</option>
              {anos.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          {municipios.length > 0 && (
            <select
              value={municipioSel}
              onChange={e => setMunicipioSel(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white flex-1 max-w-xs"
            >
              <option value="">Todos os municípios</option>
              {municipios.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          )}
          {(anoInicio || anoFim || municipioSel) && (
            <button
              onClick={() => { setAnoInicio(''); setAnoFim(''); setMunicipioSel(''); }}
              className="text-xs text-slate-500 hover:text-slate-300 underline"
            >
              Limpar filtros
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">

          {/* Estado vazio */}
          {!temDados && (
            <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
              <Database className="w-12 h-12 text-slate-700" />
              <div>
                <p className="text-slate-400 font-medium">Nenhum dado importado</p>
                <p className="text-slate-600 text-sm mt-1">
                  Importe os arquivos CSV da rede pública do MS (2018–2026) para começar.
                </p>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded-lg text-sm transition-colors"
              >
                <Upload className="w-4 h-4" /> Importar CSV
              </button>
            </div>
          )}

          {/* Painel admin — lista de anos */}
          {userRole === 'administrador' && temDados && anos.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Anos importados
              </h2>
              <div className="flex flex-wrap gap-2">
                {anos.map(ano => (
                  <div
                    key={ano}
                    className="flex items-center gap-1.5 px-3 py-1 bg-slate-800 rounded-lg"
                  >
                    <span className="text-sm text-white">{ano}</span>
                    <button
                      onClick={() => handleDeleteAno(ano)}
                      className="p-0.5 text-slate-600 hover:text-red-400 transition-colors"
                      title={`Excluir dados de ${ano}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {temDados && (
            <>
              {/* KPIs */}
              {dashData.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {kpis.map(k => (
                    <div key={k.label} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 mb-1">{k.label}</p>
                      <p className="text-2xl font-bold" style={{ color: k.color }}>{k.value}</p>
                    </div>
                  ))}
                </div>
              )}

              {loading && (
                <div className="text-center text-slate-500 py-8">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                  Carregando dados…
                </div>
              )}

              {dashData.length === 0 && !loading && (
                <div className="flex items-center gap-3 bg-yellow-950/40 border border-yellow-800/50 rounded-xl p-4 text-yellow-300 text-sm">
                  <AlertTriangle className="w-5 h-5 shrink-0" />
                  Sem dados para os filtros selecionados.
                </div>
              )}

              {/* Toggle de colunas */}
              {dashData.length > 0 && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    Colunas nos gráficos
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {ALL_COLS.map((col, i) => (
                      <button
                        key={col.key}
                        onClick={() => toggleCol(col.key)}
                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                          colunasSel.includes(col.key)
                            ? 'text-white border-transparent'
                            : 'text-slate-500 border-slate-700 hover:border-slate-500'
                        }`}
                        style={
                          colunasSel.includes(col.key)
                            ? { backgroundColor: PALETTE[i % PALETTE.length] + '33',
                                borderColor: PALETTE[i % PALETTE.length],
                                color: PALETTE[i % PALETTE.length] }
                            : {}
                        }
                      >
                        {col.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Gráfico de linha */}
              {dashData.length > 0 && colunasSel.length > 0 && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <h2 className="text-sm font-semibold text-slate-300 mb-4">
                    Evolução por Ano
                    {municipioSel ? ` — ${municipioSel}` : ''}
                    {(anoInicio || anoFim) ? ` (${anoInicio || '...'} → ${anoFim || '...'})` : ''}
                  </h2>
                  <ResponsiveContainer width="100%" height={440}>
                    <LineChart data={dashData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="ano" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                        labelStyle={{ color: '#e2e8f0' }}
                        allowEscapeViewBox={{ x: false, y: true }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {colunasSel.map((key, i) => {
                        const col = ALL_COLS.find(c => c.key === key);
                        return (
                          <Line
                            key={key}
                            type="monotone"
                            dataKey={key}
                            name={col?.label ?? key}
                            stroke={PALETTE[i % PALETTE.length]}
                            strokeWidth={2}
                            dot={dashData.length <= 15}
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Gráfico de barras */}
              {dashData.length > 0 && colunasSel.length > 0 && (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <h2 className="text-sm font-semibold text-slate-300 mb-4">
                    Comparativo por Ano
                  </h2>
                  <ResponsiveContainer width="100%" height={440}>
                    <BarChart data={dashData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="ano" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                        allowEscapeViewBox={{ x: false, y: true }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {colunasSel.map((key, i) => {
                        const col = ALL_COLS.find(c => c.key === key);
                        return (
                          <Bar
                            key={key}
                            dataKey={key}
                            name={col?.label ?? key}
                            fill={PALETTE[i % PALETTE.length]}
                            radius={[3, 3, 0, 0]}
                          />
                        );
                      })}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Chat Analítico ── */}
      <div className="w-96 flex flex-col border-l border-slate-800 bg-slate-900/40">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2 shrink-0">
          <Bot className="w-5 h-5 text-blue-400" />
          <div>
            <p className="text-sm font-semibold">Nexus IA</p>
            <p className="text-xs text-slate-500 truncate max-w-[200px]">{filtrosDesc}</p>
          </div>
        </div>

        <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.length === 0 && !streamingAI && (
            <div className="text-center text-slate-600 text-sm mt-8 space-y-2">
              <Bot className="w-10 h-10 mx-auto text-slate-700" />
              <p>Pergunte sobre os dados educacionais.</p>
              <p className="text-xs">Ex: "Qual foi a taxa de abandono em 2022?" ou "Compare aprovação e reprovação ao longo dos anos."</p>
              {!temDados && <p className="text-yellow-600 text-xs mt-2">Importe os CSVs para começar.</p>}
            </div>
          )}

          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === 'user' ? 'bg-blue-700 text-white' : 'bg-slate-800 text-slate-200'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {streamingAI && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-xl px-3 py-2 text-sm bg-slate-800 text-slate-200 leading-relaxed whitespace-pre-wrap">
                {streamingAI}
                <span className="inline-block w-1.5 h-4 bg-blue-400 ml-1 animate-pulse align-middle" />
              </div>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-slate-800 shrink-0">
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
