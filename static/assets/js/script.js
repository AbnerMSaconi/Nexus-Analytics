/* UCDB-IA | Lógica de Mensageiro (Bolhas Alinhadas) */

window.onload = () => {
    // Referências
    const corpo = document.body;
    const btnEsq = document.getElementById('btn-lateral-esquerda');
    const btnDir = document.getElementById('btn-lateral-direita');
    const painelEsq = document.getElementById('painel-conhecimento');
    const painelDir = document.getElementById('painel-fontes');
    const listaMateriais = document.getElementById('lista-materiais');
    const areaFontes = document.getElementById('conteudo-fontes');
    
    const painelChat = document.getElementById('fluxo-conversa');
    const entradaHome = document.getElementById('entrada-inicial');
    const entradaChat = document.getElementById('entrada-usuario');
    const btnHome = document.getElementById('btn-enviar-inicial');
    const btnChat = document.getElementById('btn-enviar');

    const iconesMap = { "Engenharias": "fa-microchip", "Direito": "fa-gavel", "Saúde": "fa-stethoscope", "Humanas": "fa-users" };
    let areaSelecionada = null;

    // --- 1. UI Toggles ---
    function toggleSidebar(lado) {
        if (lado === 'esquerda') {
            painelEsq.classList.toggle('visivel');
            btnEsq.classList.toggle('ativo');
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

    function ativarModoChat(msg = "") {
        if (corpo.classList.contains('estado-inicial')) {
            corpo.classList.remove('estado-inicial');
            setTimeout(() => { painelChat.scrollTop = painelChat.scrollHeight; }, 100);
        }
        if (msg) {
            entradaChat.value = msg;
            executarConsulta();
        }
    }

    // --- 2. Criação de Mensagens (Estrutura Row + Bubble) ---
    function adicionarMensagem(tipo, conteudo) {
        // 1. Cria a linha (Trilho)
        const linha = document.createElement('div');
        linha.className = `chat-row ${tipo === 'user' ? 'user' : 'bot'}`;
        
        // 2. Cria a bolha visual
        const bolha = document.createElement('div');
        bolha.className = `msg-bubble ${tipo === 'user' ? 'usuario' : 'bot'}`;
        
        // 3. Conteúdo (Texto ou Markdown)
        const inner = document.createElement('div');
        inner.className = 'conteudo-texto';
        
        if (tipo === 'user') inner.textContent = conteudo;
        else inner.innerHTML = marked.parse(conteudo);
        
        bolha.appendChild(inner);
        linha.appendChild(bolha);
        painelChat.appendChild(linha);
        
        painelChat.scrollTop = painelChat.scrollHeight;
        return linha; // Retorna a linha para controle
    }

    async function executarConsulta() {
        const texto = entradaChat.value.trim();
        if (!texto || btnChat.disabled) return;

        adicionarMensagem('user', texto);
        entradaChat.value = '';
        entradaChat.style.height = '24px';
        btnChat.disabled = true;

        const linhaBot = adicionarMensagem('ai', '...');
        const alvo = linhaBot.querySelector('.conteudo-texto'); // Busca o alvo dentro da bolha
        let buffer = '';

        try {
            // AGORA ENVIAMOS A ÁREA NO CORPO DO JSON
            const payload = { 
                message: texto,
                area: areaSelecionada // <--- NOVO CAMPO
            };

            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            alvo.innerHTML = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    alvo.innerHTML = marked.parse(buffer);
                    if (window.MathJax) MathJax.typesetPromise([alvo]);
                    break;
                }
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n\n');
                lines.forEach(line => {
                    if (line.startsWith('data:')) {
                        try {
                            const data = JSON.parse(line.replace('data: ', '').trim());
                            if (data.type === 'start') alvo.innerHTML = '<i><i class="fas fa-spinner fa-spin"></i> Processando...</i>';
                            else if (data.type === 'chunk') {
                                buffer = data.content;
                                alvo.textContent = buffer + ' ▎';
                                painelChat.scrollTop = painelChat.scrollHeight;
                            } else if (data.type === 'source_chunks') {
                                renderizarReferencias(data.content);
                                if (window.innerWidth > 1000 && !painelDir.classList.contains('visivel')) {
                                    toggleSidebar('direita');
                                }
                            }
                        } catch (e) {}
                    }
                });
            }
        } catch (e) { alvo.innerHTML = '<span style="color:red">Erro de conexão.</span>'; }
        finally { btnChat.disabled = false; }
    }
    // --- Atualizar os Listeners dos Cards ---
    document.querySelectorAll('.card-area').forEach(c => {
        c.onclick = () => {
            // Captura o nome exato da pasta (ex: "Engenharias")
            // Certifique-se que o data-area no HTML bate com o nome da pasta no Windows/Linux
            areaSelecionada = c.getAttribute('data-area'); 
            
            ativarModoChat(`Olá Especialista em ${areaSelecionada}, tenho uma dúvida.`);
        };
    });

    function renderizarReferencias(fontes) {
        areaFontes.innerHTML = '';
        if(!fontes || fontes.length === 0) {
            areaFontes.innerHTML = '<p class="vazio">Sem citações.</p>';
            return;
        }
        fontes.forEach(f => {
            const el = document.createElement('div');
            el.className = 'source-chunk';
            el.innerHTML = `<strong><i class="fas fa-file-pdf"></i> ${f.source}</strong><p>${f.content}</p>`;
            areaFontes.appendChild(el);
        });
    }

    // --- 3. Inicialização e Listeners ---
    (async () => {
        try {
            const res = await fetch('/knowledge-areas');
            const data = await res.json();
            const cats = data.categorias || {};
            listaMateriais.innerHTML = Object.keys(cats).length ? '' : '<div style="padding:15px;color:#64748b">Vazio</div>';
            
            Object.keys(cats).forEach(cat => {
                const div = document.createElement('div');
                div.className = 'sidebar-block';
                div.innerHTML = `<div class="block-header"><i class="fas ${iconesMap[cat]||'fa-folder'}"></i><span>${cat}</span></div><ul class="block-list">${cats[cat].map(t=>`<li title="${t}"><i class="far fa-file-pdf"></i> ${t.substring(0,28)}...</li>`).join('')}</ul>`;
                listaMateriais.appendChild(div);
            });
        } catch(e) {}
    })();

    document.getElementById('btn-enviar-inicial').onclick = () => ativarModoChat(document.getElementById('entrada-inicial').value);
    btnChat.onclick = executarConsulta;
    
    document.querySelectorAll('.card-area').forEach(c => c.onclick = () => ativarModoChat(`Olá Especialista em ${c.dataset.area}, gostaria de tirar uma dúvida.`));

    [document.getElementById('entrada-inicial'), entradaChat].forEach(el => {
        el.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                el.id === 'entrada-inicial' ? ativarModoChat(el.value) : executarConsulta();
            }
        };
        el.oninput = function() {
            this.style.height = '24px';
            if (this.scrollHeight > 30) this.style.height = this.scrollHeight + 'px';
        };
    });
};