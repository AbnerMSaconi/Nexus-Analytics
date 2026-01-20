/* UCDB-IA | Lógica de Interface (Sidebars Off-Canvas) */

window.onload = () => {
    // --- Referências ---
    const corpo = document.body;
    const btnEsq = document.getElementById('btn-lateral-esquerda');
    const btnDir = document.getElementById('btn-lateral-direita');
    const painelEsq = document.getElementById('painel-conhecimento');
    const painelDir = document.getElementById('painel-fontes');
    const listaMateriais = document.getElementById('lista-materiais');
    const areaFontes = document.getElementById('conteudo-fontes');
    
    // Áreas de Conteúdo e Chat
    const painelChat = document.getElementById('fluxo-conversa');
    const entradaHome = document.getElementById('entrada-inicial');
    const entradaChat = document.getElementById('entrada-usuario');
    const btnHome = document.getElementById('btn-enviar-inicial');
    const btnChat = document.getElementById('btn-enviar');

    const iconesMap = { "Engenharias": "fa-microchip", "Direito": "fa-gavel", "Saúde": "fa-stethoscope", "Humanas": "fa-users" };

    // --- 1. Lógica de Alternância das Sidebars (Toggle) ---
    
    function toggleSidebar(lado) {
        if (lado === 'esquerda') {
            painelEsq.classList.toggle('visivel');
            btnEsq.classList.toggle('ativo'); // Feedback visual no botão
            // Fecha a direita se estiver aberta (opcional, bom para mobile)
            if (window.innerWidth < 1000) {
                painelDir.classList.remove('visivel');
                btnDir.classList.remove('ativo');
            }
        } else {
            painelDir.classList.toggle('visivel');
            btnDir.classList.toggle('ativo');
            if (window.innerWidth < 1000) {
                painelEsq.classList.remove('visivel');
                btnEsq.classList.remove('ativo');
            }
        }
    }

    btnEsq.onclick = () => toggleSidebar('esquerda');
    btnDir.onclick = () => toggleSidebar('direita');

    // --- 2. Transição Home -> Chat ---
    function ativarModoChat(msg = "") {
        if (corpo.classList.contains('estado-inicial')) {
            corpo.classList.remove('estado-inicial');
            // Garante scroll no fim
            setTimeout(() => { painelChat.scrollTop = painelChat.scrollHeight; }, 50);
        }
        if (msg) {
            entradaChat.value = msg;
            executarConsulta();
        }
    }

    // --- 3. Chat e Streaming ---
    function criarMsg(tipo, htmlContent) {
        const div = document.createElement('div');
        div.className = `msg ${tipo === 'user' ? 'usuario' : 'bot'}`;
        
        // Se for user, texto puro (segurança). Se bot, HTML (Markdown)
        if(tipo === 'user') div.textContent = htmlContent;
        else div.innerHTML = htmlContent;

        painelChat.appendChild(div);
        painelChat.scrollTop = painelChat.scrollHeight;
        return div;
    }

    async function executarConsulta() {
        const texto = entradaChat.value.trim();
        if (!texto || btnChat.disabled) return;

        criarMsg('user', texto);
        entradaChat.value = '';
        entradaChat.style.height = 'auto';
        btnChat.disabled = true;

        const botMsg = criarMsg('ai', '...'); // Placeholder
        let buffer = '';

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: texto })
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            botMsg.innerHTML = ''; // Limpa o "..."

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    botMsg.innerHTML = marked.parse(buffer);
                    if (window.MathJax) MathJax.typesetPromise([botMsg]);
                    break;
                }
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n\n');
                lines.forEach(line => {
                    if (line.startsWith('data:')) {
                        try {
                            const data = JSON.parse(line.replace('data: ', '').trim());
                            if (data.type === 'start') botMsg.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Analisando...';
                            else if (data.type === 'chunk') {
                                buffer = data.content;
                                botMsg.textContent = buffer + ' ▎';
                                painelChat.scrollTop = painelChat.scrollHeight;
                            } else if (data.type === 'source_chunks') {
                                renderizarReferencias(data.content);
                                // Opcional: Abrir sidebar direita automaticamente quando chegarem fontes
                                // if (!painelDir.classList.contains('visivel')) toggleSidebar('direita');
                            }
                        } catch (e) {}
                    }
                });
            }
        } catch (e) {
            botMsg.innerHTML = '<span style="color:#ef4444">Erro de conexão.</span>';
        } finally {
            btnChat.disabled = false;
        }
    }

    // --- 4. Renderizadores de Conteúdo ---
    function renderizarReferencias(fontes) {
        areaFontes.innerHTML = '';
        if(!fontes || fontes.length === 0) {
            areaFontes.innerHTML = '<p style="color:#64748b; padding:10px">Sem fontes citadas.</p>';
            return;
        }
        fontes.forEach(f => {
            const el = document.createElement('div');
            el.className = 'source-chunk';
            el.innerHTML = `<strong><i class="fas fa-file-pdf"></i> ${f.source}</strong><p>${f.content}</p>`;
            areaFontes.appendChild(el);
        });
    }

    async function carregarSidebar() {
        try {
            const res = await fetch('/knowledge-areas');
            const data = await res.json();
            const cats = data.categorias || {};
            listaMateriais.innerHTML = '';
            
            if(Object.keys(cats).length === 0) {
                listaMateriais.innerHTML = '<div style="padding:15px; color:#64748b">Repositório vazio.</div>';
                return;
            }

            Object.keys(cats).forEach(cat => {
                const div = document.createElement('div');
                div.className = 'sidebar-block';
                div.innerHTML = `
                    <div class="block-header"><i class="fas ${iconesMap[cat] || 'fa-folder'}"></i> <span>${cat}</span></div>
                    <ul class="block-list">${cats[cat].map(t => `<li><i class="far fa-file-alt"></i> ${t.substring(0,35)}...</li>`).join('')}</ul>
                `;
                listaMateriais.appendChild(div);
            });
        } catch (e) { console.error(e); }
    }

    // --- 5. Listeners ---
    btnHome.onclick = () => ativarModoChat(entradaHome.value);
    btnChat.onclick = executarConsulta;
    
    document.querySelectorAll('.card-area').forEach(c => {
        c.onclick = () => ativarModoChat(`Olá, preciso de ajuda com ${c.getAttribute('data-area')}.`);
    });

    [entradaHome, entradaChat].forEach(el => {
        el.onkeydown = (e) => {
            if(e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                el === entradaHome ? btnHome.click() : btnChat.click();
            }
        };
        el.oninput = function() { this.style.height = 'auto'; this.style.height = this.scrollHeight + 'px'; };
    });

    carregarSidebar();
};