# 🛠️ UCDB-IA Maintenance MCP Server

Este é um servidor **Model Context Protocol (MCP)** projetado para auxiliar no desenvolvimento e manutenção do projeto **UCDB-IA**. Ele permite que IAs gerenciem usuários, auditem logs e monitorem a saúde do sistema diretamente através de ferramentas padronizadas.

## 🚀 Como Configurar

### 1. Requisitos
Certifique-se de ter o Python 3.10+ instalado.

### 2. Instalação
Instale o SDK do MCP e as dependências necessárias:
```bash
pip install mcp sqlalchemy
```

### 3. Integração com Claude Desktop
Para usar este servidor no Claude Desktop, adicione o seguinte ao seu arquivo `claude_desktop_config.json`:

**No Windows:**
```json
{
  "mcpServers": {
    "ucdb-ia-admin": {
      "command": "python",
      "args": [
        "C:/Caminho/Para/Seu/Projeto/UCDB-IA-main/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "C:/Caminho/Para/Seu/Projeto/UCDB-IA-main"
      }
    }
  }
}
```

## 🛠️ Ferramentas Disponíveis

| Ferramenta | Descrição |
| :--- | :--- |
| `list_users` | Lista usuários recentes, cargos e status de bloqueio. |
| `promote_user_to_admin` | Eleva o nível de acesso de um usuário para administrador. |
| `unlock_user` | Desbloqueia contas que excederam tentativas de login. |
| `get_audit_logs` | Recupera logs de auditoria para investigação de incidentes. |
| `system_health_check` | Visão geral da saúde do banco de dados e erros recentes. |

## 🧪 Desenvolvimento
Para testar o servidor localmente durante o desenvolvimento:
```bash
python mcp_server/server.py
```
*O servidor iniciará em modo de transporte via stdio, aguardando comandos JSON-RPC.*
