# Diretrizes e Regras do Sistema UCDB-IA

Este documento define as regras de negócio, hierarquia e padrões de segurança para a plataforma de Inteligência Artificial da **Universidade Católica Dom Bosco (UCDB)**.

## 1. Hierarquia e Controle de Acesso (RBAC)

O sistema opera sob uma estrutura rígida de permissões para garantir a integridade dos dados acadêmicos:

*   **Administrador (TI/Reitoria):**
    *   Acesso total ao sistema.
    *   Gestão global de usuários (criar, editar, excluir, promover).
    *   Gestão de todas as bases de conhecimento (PDFs).
    *   Acesso a logs de auditoria e monitoramento de performance.

*   **Coordenador (Gestão de Curso):**
    *   **Escopo Restrito:** Atua apenas sobre os cursos que coordena.
    *   **Gestão de Alunos:** Pode cadastrar, editar e excluir apenas usuários com cargo `aluno` pertencentes à sua área.
    *   **Múltiplos Cursos:** Um coordenador pode gerenciar N cursos (ex: Direito e Psicologia).
    *   **Base de Dados:** Gerencia os documentos (PDFs) específicos de sua coordenação.

*   **Professor (Docente):**
    *   **Acesso a Conteúdo:** Pode visualizar e gerenciar documentos das áreas em que leciona.
    *   **Chat Especializado:** Acesso ao RAG das áreas associadas ao seu perfil e à área "Geral".
    *   **Sem Gestão de Usuários:** Não possui acesso ao painel de matrículas.

*   **Aluno (Discente):**
    *   **Acesso Restrito:** Apenas ao chat e histórico pessoal.
    *   **Regra de Matrícula:** Pode estar vinculado a no máximo 2 cursos simultâneos.
    *   **Filtro de Conteúdo:** Só pode interagir com a IA usando documentos de seu curso ou da base "Geral".

## 2. Padrões de Dados e Identidade

*   **Identificador Único (RA):** O login deve ser obrigatoriamente o Registro Acadêmico (RA).
*   **Insensibilidade a Caso (Case-Insensitivity):** O sistema deve tratar `RA123`, `ra123` e `Ra123` como o mesmo usuário. Cursos e Cargos também seguem esta regra.
*   **Padronização de Strings:** Todos os identificadores, cargos e cursos são normalizados para letras minúsculas no banco de dados para evitar conflitos de busca.

## 3. Segurança e Auditoria

*   **Proteção de Conta:** Bloqueio automático após 5 tentativas falhas de login.
*   **Logs de Auditoria:** Todas as ações sensíveis (login, upload de arquivos, exclusão de usuários, alteração de cargo) são registradas com timestamp e IP.
*   **Privacidade:** O conteúdo das conversas no banco de dados deve ser criptografado em repouso.
*   **Prevenção de Injeção:** Filtros ativos contra *Prompt Injection* no chat para evitar que usuários manipulem as instruções da IA.

## 4. Regras de Processamento de Documentos (RAG)

*   **Privacidade por Área:** Documentos de um curso (ex: Direito) nunca devem ser acessíveis por alunos de outro curso (ex: Veterinária).
*   **Base Geral:** Conteúdos de interesse comum (Manuais, Calendários) ficam na área "Geral", acessível a todos.
*   **Integridade:** Arquivos digitalizados (apenas imagem) são ignorados para garantir que apenas informações textuais verificáveis sejam processadas pela IA.

---
*Última atualização: Maio de 2026*
