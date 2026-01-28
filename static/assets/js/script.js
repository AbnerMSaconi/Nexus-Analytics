// static/assets/js/script.js - Versão Completa e Integrada

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Referências aos Elementos (Mapeamento Completo) ---
    const body = document.body;
    
    // Chat Principal
    const chatContainer = document.getElementById('fluxo-conversa');
    const mainInput = document.getElementById('entrada-usuario');
    const mainBtn = document.getElementById('btn-enviar');
    
    // Tela de Boas-Vindas
    const welcomeInput = document.getElementById('entrada-inicial');
    const welcomeBtn = document.getElementById('btn-enviar-inicial');
    
    // Sidebars (Paineis Laterais)
    const btnLeft = document.getElementById('btn-lateral-esquerda');
    const btnRight = document.getElementById('btn-lateral-direita');
    const panelLeft = document.getElementById('painel-conhecimento');
    const panelRight = document.getElementById('painel-fontes');
    const materialsList = document.getElementById('lista-materiais');

    // --- 2. Controle de Interface (Sidebars e Transição) ---

    // Função para abrir/fechar barras laterais
    function toggleSidebar(side) {
        if (side === 'left') {
            panelLeft.classList.toggle('visivel');
            btnLeft.classList.toggle('ativo');
            // Fecha a outra se estiver em mobile
            if (window.innerWidth < 1000) {
                panelRight.classList.remove('visivel');
                btnRight.classList.remove('ativo');
            }
        } else {
            panelRight.classList.toggle('visivel');
            btnRight.classList.toggle('ativo');
            if (window.innerWidth < 1000) {
                panelLeft.classList.remove('visivel');
                btnLeft.classList.remove('ativo');
            }
        }
    }

    // Listeners das Sidebars
    if (btnLeft) btnLeft.onclick = () => toggleSidebar('left');
    if (btnRight) btnRight.onclick = () => toggleSidebar('right');

    // Função para sair do modo "Boas-Vindas" e ir para o Chat
    function activateChatMode() {
        if (body.classList.contains('estado-inicial')) {
            body.classList.remove('estado-inicial');
            // Pequeno delay para o layout se ajustar antes de scrollar
            setTimeout(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
                mainInput.focus();
            }, 300);
        }
    }

    // --- 3. Lógica do Chat (Envio e Renderização) ---

    function addMessage(role, content = '') {
        const row = document.createElement('div');
        row.className = `chat-row ${role === 'user' ? 'user' : 'bot'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `msg-bubble ${role === 'user' ? 'usuario' : 'bot'}`;
        
        const innerContent = document.createElement('div');
        innerContent.className = 'conteudo-texto';
        
        if (role === 'ai') {
            innerContent.innerHTML = marked.parse(content);
        } else {
            innerContent.textContent = content;
        }
        
        bubble.appendChild(innerContent);

        if (role === 'ai') {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'sources-container';
            sourcesDiv.style.display = 'none';
            sourcesDiv.style.marginTop = '12px';
            sourcesDiv.style.paddingTop = '8px';
            sourcesDiv.style.borderTop = '1px solid rgba(255,255,255,0.1)';
            sourcesDiv.style.fontSize = '0.85em';
            bubble.appendChild(sourcesDiv);
        }

        row.appendChild(bubble);
        chatContainer.appendChild(row);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        return row;
    }

    // Carrega Assuntos na Sidebar Esquerda
    async function loadKnowledgeAreas() {
        try {
            const response = await fetch('/knowledge-areas');
            const data = await response.json();
            const areas = data.areas || [];
            
            if (materialsList) {
                materialsList.innerHTML = '';
                if (areas.length === 0) materialsList.innerHTML = '<div style="padding:15px; color:#aaa; font-style:italic">Vazio.</div>';
                
                areas.forEach(area => {
                    const item = document.createElement('div');
                    item.className = 'sidebar-block';
                    item.innerHTML = `
                        <div class="block-header" style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); cursor:pointer;">
                            <i class="fas fa-book" style="margin-right:8px; color:#3b82f6;"></i> ${area}
                        </div>`;
                    // Clique no assunto inicia chat sobre ele
                    item.onclick = () => sendMessage(`Gostaria de saber mais sobre ${area}`);
                    materialsList.appendChild(item);
                });
            }
        } catch (e) {
            console.error("Erro ao carregar áreas:", e);
        }
    }

    // Função Principal de Envio
    async function sendMessage(textOverride = null) {
        // Decide de onde pegar o texto: argumento, input inicial ou input principal
        let text = textOverride;
        
        if (!text) {
            if (body.classList.contains('estado-inicial')) {
                text = welcomeInput.value.trim();
                welcomeInput.value = '';
            } else {
                text = mainInput.value.trim();
                mainInput.value = '';
                mainInput.style.height = '24px';
            }
        }

        if (!text) return;

        // 1. Transição visual
        activateChatMode();
        
        // 2. Adiciona mensagem do usuário
        addMessage('user', text);
        
        // 3. Trava interface
        mainBtn.disabled = true;

        // 4. Cria bolha do bot
        const botRow = addMessage('ai', '<i class="fas fa-circle-notch fa-spin"></i> Processando...');
        const contentDiv = botRow.querySelector('.conteudo-texto');
        const sourcesDiv = botRow.querySelector('.sources-container');
        
        let buffer = "";

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: text })
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            contentDiv.innerHTML = ''; 

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const json = JSON.parse(line.substring(6));
                            
                            if (json.type === 'chunk') {
                                buffer += json.content;
                                contentDiv.innerHTML = marked.parse(buffer);
                                if (window.MathJax) MathJax.typesetPromise([contentDiv]);
                            } 
                            else if (json.type === 'sources') {
                                if (json.content && json.content.length > 0) {
                                    sourcesDiv.style.display = 'block';
                                    const linksHtml = json.content.map(src => {
                                        const parts = src.split('|');
                                        const path = parts[0]; 
                                        const pages = parts[1] || '?';
                                        const filename = path.split('/').pop();
                                        return `
                                            <li style="margin-bottom: 4px;">
                                                <a href="/pdfs/${path}" target="_blank" style="color: #60a5fa; text-decoration: underline;">
                                                    <i class="far fa-file-pdf"></i> ${filename}
                                                </a>
                                                <span style="color:#94a3b8; font-size:0.9em;">(pág. ${pages})</span>
                                            </li>`;
                                    }).join('');
                                    sourcesDiv.innerHTML = `<strong>Referências:</strong><ul style="list-style:none; padding-left:0; margin-top:5px;">${linksHtml}</ul>`;
                                    
                                    // Abre sidebar direita automaticamente em telas grandes
                                    if (window.innerWidth > 1000 && !panelRight.classList.contains('visivel')) {
                                        toggleSidebar('right');
                                    }
                                }
                            }
                            else if (json.type === 'error') {
                                contentDiv.innerHTML += `<br><span style="color:#ef4444">Erro: ${json.content}</span>`;
                            }
                            
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        } catch (e) {}
                    }
                }
            }
        } catch (e) {
            contentDiv.innerHTML += '<br><span style="color:red">Erro de conexão.</span>';
        } finally {
            mainBtn.disabled = false;
            // Foca no input principal para a próxima mensagem
            mainInput.focus();
        }
    }

    // --- 4. Listeners de Eventos ---

    // Botão Enviar (Tela Inicial)
    if (welcomeBtn) welcomeBtn.addEventListener('click', () => sendMessage());
    
    // Input Enter (Tela Inicial)
    if (welcomeInput) {
        welcomeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Botão Enviar (Chat Principal)
    if (mainBtn) mainBtn.addEventListener('click', () => sendMessage());

    // Input Enter (Chat Principal)
    if (mainInput) {
        mainInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        // Auto-resize
        mainInput.addEventListener('input', function() {
            this.style.height = '24px';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }

    // Cards de Áreas (Engenharia, Direito, etc.)
    document.querySelectorAll('.card-area').forEach(card => {
        card.addEventListener('click', () => {
            const area = card.getAttribute('data-area');
            sendMessage(`Olá, gostaria de tirar dúvidas sobre a área de ${area}.`);
        });
    });

    // Inicia
    loadKnowledgeAreas();
});