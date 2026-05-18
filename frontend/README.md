# Nexus — Frontend

Interface web do Nexus, construída com React 18 + TypeScript + TailwindCSS.

## Stack

- **React 18** + **TypeScript**
- **TailwindCSS** para estilização
- **Recharts** para gráficos
- **react-markdown** + **KaTeX** para renderização de markdown e LaTeX nas respostas do chat
- **react-router-dom** para navegação
- **Vite** como bundler e servidor de desenvolvimento

## Desenvolvimento

```bash
npm install
npm run dev
```

O servidor sobe em `http://localhost:5173`. Em produção (Docker), o endereço do backend é resolvido dinamicamente via `window.location.hostname`, permitindo acesso por qualquer PC na rede local.

## Estrutura

```
src/
├── components/
│   ├── DashboardDAC.tsx     # Dashboard principal com gráficos e chat analítico
│   ├── AdminPanel.tsx       # Painel administrativo (usuários, status, importação)
│   ├── SystemStatus.tsx     # Status dos serviços e monitoramento de GPU
│   ├── DocumentManager.tsx  # Gerenciamento de documentos RAG
│   ├── MarkdownMessage.tsx  # Renderizador de markdown + LaTeX (KaTeX)
│   ├── Login.tsx            # Tela de autenticação
│   └── Layout.tsx           # Layout base com navegação lateral
├── services/
│   ├── apiService.ts        # Integração com o backend RAG
│   └── storageService.ts    # Persistência de sessões
├── assets/
│   └── api.ts               # Funções de chamada à API REST
├── utils/
│   └── apiBase.ts           # URL base dinâmica (window.location.hostname:8000)
└── types.ts                 # Tipos compartilhados
```
