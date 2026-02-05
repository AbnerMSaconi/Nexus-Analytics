// static/assets/js/script.js - Versão v6.0 (Normalização e Correção MathJax)

console.log("Script v6.0 carregado - Normalização Ativa");

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. CONFIGURAÇÃO MATHJAX ROBUSTA ---
    // Define configurações globais antes mesmo do MathJax carregar
    window.MathJax = {
        tex: {
            // Aceita tudo: $, $$, \(, \), \[, \]
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$', '$$'], ['\\[', '\\]']],
            processEscapes: true,
            processEnvironments: true
        },
        svg: { fontCache: 'global' },
        startup: {
            typeset: false // Vamos chamar manualmente para evitar conflitos
        }
    };

    // --- REFERÊNCIAS ---
    const body = document.body;
    const chatContainer = document.getElementById('fluxo-conversa');
    const welcomeTitle = document.getElementById('titulo-boas-vindas');
    const buttonsArea = document.getElementById('area-botoes');
    const overlay = document.getElementById('overlay-mobile');

    const welcomeInput = document.getElementById('entrada-inicial');
    const welcomeBtn = document.getElementById('btn-enviar-inicial');
    const mainInput = document.getElementById('entrada-usuario');
    const mainBtn = document.getElementById('btn-enviar');

    const sidebarList = document.getElementById('lista-materiais');
    const sourcesContent = document.getElementById('conteudo-fontes');
    const btnLeft = document.getElementById('btn-lateral-esquerda');
    const btnRight = document.getElementById('btn-lateral-direita');
    const pnLeft = document.getElementById('painel-conhecimento');
    const pnRight = document.getElementById('painel-fontes');

    // --- 2. MOTOR DE RENDERIZAÇÃO INTELIGENTE ---

    function renderMarkdownWithMath(text) {
        if (!text) return '';

        // PASSO A: Normalização (Padroniza a bagunça do modelo)
        // Converte \[...\] para $$...$$
        let normalizedText = text.replace(/\\\[/g, '$$$$').replace(/\\\]/g, '$$$$');
        // Converte \(...\) para $...$
        normalizedText = normalizedText.replace(/\\\(/g, '$').replace(/\\\)/g, '$');

        // PASSO B: Proteção (Esconde do Markdown)
        const mathBlocks = [];

        // Protege Blocos $$...$$
        let protectedText = normalizedText.replace(/(\$\$[\s\S]*?\$\$)/g, (match) => {
            mathBlocks.push(match);
            return `MATHBLOCK${mathBlocks.length - 1}ENDMATHBLOCK`;
        });

        // Protege Inline $...$
        protectedText = protectedText.replace(/(\$[^$\n]+?\$)/g, (match) => {
            mathBlocks.push(match);
            return `MATHBLOCK${mathBlocks.length - 1}ENDMATHBLOCK`;
        });

        // PASSO C: Renderiza Markdown (Texto e formatação)
        let html = marked.parse(protectedText);

        // PASSO D: Restaura Fórmulas
        html = html.replace(/MATHBLOCK(\d+)ENDMATHBLOCK/g, (_, index) => {
            return mathBlocks[index];
        });

        return html;
    }

    function triggerMathJax(element) {
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([element]).catch((err) => {
                console.warn('MathJax Error:', err);
                // Fallback: Tenta limpar e renderizar de novo se der erro
                if (window.MathJax.typesetClear) window.MathJax.typesetClear([element]);
            });
        }
    }

    function autoResize(el) {
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = el.scrollHeight + 'px';
    }

    // --- 3. UI HELPERS ---

    function closeAllSidebars() {
        pnLeft.classList.remove('visivel');
        btnLeft.classList.remove('ativo');
        pnRight.classList.remove('visivel');
        btnRight.classList.remove('ativo');
        if (overlay) overlay.classList.remove('ativo');
    }

    function toggleSidebar(side) {
        const isMobile = window.innerWidth < 1000;
        const panel = side === 'left' ? pnLeft : pnRight;
        const btn = side === 'left' ? btnLeft : btnRight;
        const otherPanel = side === 'left' ? pnRight : pnLeft;
        const otherBtn = side === 'left' ? btnRight : btnLeft;

        if (!panel.classList.contains('visivel')) {
            otherPanel.classList.remove('visivel');
            otherBtn.classList.remove('ativo');
            panel.classList.add('visivel');
            btn.classList.add('ativo');
            if (isMobile && overlay) overlay.classList.add('ativo');
        } else {
            panel.classList.remove('visivel');
            btn.classList.remove('ativo');
            if (isMobile) closeAllSidebars();
        }
    }

    function showSpecialistScreen(areaName) {
        welcomeTitle.textContent = `Olá, eu sou o especialista em ${areaName}.`;
        if (buttonsArea) buttonsArea.style.display = 'none';
        welcomeInput.focus();
        welcomeInput.placeholder = `Pergunte sobre ${areaName}...`;
    }

    function activateChat() {
        body.classList.remove('estado-inicial');
        chatContainer.style.display = 'flex';
    }

    // --- 4. FLUXO DE MENSAGEM ---

    function addMessage(role, content = '') {
        const isUser = role === 'user';
        const row = document.createElement('div');
        row.className = `chat-row ${isUser ? 'user' : 'bot'}`;

        const bubble = document.createElement('div');
        bubble.className = `msg-bubble ${isUser ? 'usuario' : 'bot'}`;

        const textDiv = document.createElement('div');
        textDiv.className = 'conteudo-texto';

        // SE for uma mensagem do BOT e contiver a tag da animação, usamos innerHTML
        // Caso contrário, usamos textContent para segurança
        if (!isUser && content.includes('typing-indicator')) {
            textDiv.innerHTML = content;
        } else if (!isUser) {
            textDiv.innerHTML = renderMarkdownWithMath(content);
        } else {
            textDiv.textContent = content;
        }

        bubble.appendChild(textDiv);
        row.appendChild(bubble);
        chatContainer.appendChild(row);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return row;
    }

    async function sendMessage(text) {
        text = text.trim();
        if (!text) return;

        // Reset de campos
        welcomeInput.value = '';
        mainInput.value = '';
        autoResize(mainInput);

        activateChat();
        if (sourcesContent) sourcesContent.innerHTML = '<p class="vazio">Buscando referências...</p>';

        addMessage('user', text);

        // Bloqueia interface para evitar múltiplos envios
        mainBtn.disabled = true;
        mainInput.disabled = true;

        // Cria o balão do bot com o indicador de carregamento (os 3 pontos)
        const botRow = addMessage('ai', `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `);
        const contentDiv = botRow.querySelector('.conteudo-texto');

                let fullText = "";
                let isFirstChunk = true;
        
                try {
                    const res = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text })
                    });
        
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
        
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
                                        if (isFirstChunk) {
                                            contentDiv.innerHTML = '';
                                            isFirstChunk = false;
                                        }
                                        fullText += json.content;
                                        let displayTexto = fullText.replace(/^[.\-\s,]+/, "");
                                        contentDiv.innerHTML = renderMarkdownWithMath(displayTexto);
                                        chatContainer.scrollTop = chatContainer.scrollHeight;
                                    }
                                    // --- ADICIONE ESTA LÓGICA PARA AS FONTES ---
                                    else if (json.type === 'sources' && json.content.length > 0) {
                                        if (sourcesContent) {
                                            sourcesContent.innerHTML = ''; // Limpa o texto "Buscando..."
                                            json.content.forEach(sourcePath => {
                                                // O backend envia o caminho relativo (ex: index_geral/documento.pdf)
                                                // Pegamos apenas o nome do arquivo para exibir
                                                const filename = sourcePath.split('/').pop();
        
                                                const item = document.createElement('div');
                                                item.className = 'source-chunk';
                                                item.innerHTML = `
                                                    <strong><i class="far fa-file-pdf"></i> ${filename}</strong>
                                                    <p><a href="/pdfs/${sourcePath}" target="_blank" style="color:var(--accent)">Visualizar PDF</a></p>
                                                `;
                                                sourcesContent.appendChild(item);
                                            });
        
                                            // Abre o sidebar de referências automaticamente se estiver no Desktop
                                            if (window.innerWidth > 1000) {
                                                pnRight.classList.add('visivel');
                                                btnRight.classList.add('ativo');
                                            }
                                        }
                                    }
                                } catch (e) {
                                    contentDiv.innerHTML = `<span style="color:red">Erro na conexão.</span>`;
                                }
                                finally {
                                    // Desbloqueia a barra de chat
                                    mainBtn.disabled = false;
                                    mainInput.disabled = false;
                                    mainInput.focus();
                                }
                            }
                            // Renderiza MathJax (Lento) APENAS no final para não travar o streaming
                            triggerMathJax(contentDiv);
                        }
                    }
                } catch (error) {
                    console.error('Erro ao enviar mensagem:', error);
                    mainBtn.disabled = false;
                    mainInput.disabled = false;
                }
            }
        
            // --- 5. LISTENERS ---
        
            function handleEnter(e, inputEl) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const val = inputEl.value;
                    if (val.trim()) sendMessage(val);
                }
            }
        
            function handleSendClick(inputEl) {
                const val = inputEl.value;
                if (val.trim()) sendMessage(val);
            }
        
            if (welcomeInput) {
                welcomeInput.addEventListener('keydown', (e) => handleEnter(e, welcomeInput));
                welcomeInput.addEventListener('input', function () { autoResize(this); });
            }
            if (mainInput) {
                mainInput.addEventListener('keydown', (e) => handleEnter(e, mainInput));
                mainInput.addEventListener('input', function () { autoResize(this); });
            }
        
            if (welcomeBtn) welcomeBtn.addEventListener('click', () => handleSendClick(welcomeInput));
            if (mainBtn) mainBtn.addEventListener('click', () => handleSendClick(mainInput));
        
            // UI Globais
            if (btnLeft) btnLeft.onclick = () => toggleSidebar('left');
            if (btnRight) btnRight.onclick = () => toggleSidebar('right');
            if (overlay) overlay.onclick = () => closeAllSidebars();
            document.querySelectorAll('.header-lateral').forEach(h => h.onclick = () => closeAllSidebars());
        
            // Swipe
            let touchStartX = 0;
            pnRight.addEventListener('touchstart', e => { touchStartX = e.changedTouches[0].screenX; }, { passive: true });
            pnRight.addEventListener('touchend', e => {
                if (e.changedTouches[0].screenX - touchStartX > 50 && pnRight.classList.contains('visivel')) toggleSidebar('right');
            }, { passive: true });
        
            // --- 6. INICIALIZAÇÃO ---
            async function init() {
                try {
                    const res = await fetch('/knowledge-areas');
                    const data = await res.json();
        
                    if (sidebarList && data.areas) {
                        sidebarList.innerHTML = '';
                        if (data.areas.length === 0) sidebarList.innerHTML = '<div style="padding:15px;color:#aaa">Vazio</div>';
        
                        data.areas.forEach(a => {
                            const d = document.createElement('div');
                            d.className = 'sidebar-block';
                            d.innerHTML = `<div style="padding:10px;cursor:pointer"><i class="fas fa-book"></i> ${a}</div>`;
                            d.onclick = () => showSpecialistScreen(a);
                            sidebarList.appendChild(d);
                        });
        
                        let welcomeText = "Olá! Sou o **UCDB-IA** 🧠.\nEstou pronto para ajudar.";
                        if (data.areas.length > 0) welcomeText += "\n\n**Vamos começar?**";
                        addMessage('ai', welcomeText);
                    }
                } catch (e) {
                    addMessage('ai', "Olá! Sou o UCDB-IA.");
                }
        
                document.querySelectorAll('.card-area').forEach(c => {
                    c.onclick = () => showSpecialistScreen(c.getAttribute('data-area'));
                });
            }
        
            init();
        });