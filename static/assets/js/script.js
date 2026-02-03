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
    const welcomeScreen = document.getElementById('tela-boas-vindas');
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
        html = html.replace(/MATHBLOCK(\d+)ENDMATHBLOCK/g, (match, index) => {
            return mathBlocks[index];
        });

        return html;
    }

    function triggerMathJax(element) {
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([element]).catch((err) => {
                console.warn('MathJax Error:', err);
                // Fallback: Tenta limpar e renderizar de novo se der erro
                if(window.MathJax.typesetClear) window.MathJax.typesetClear([element]);
            });
        }
    }

    function autoResize(el) {
        if(!el) return;
        el.style.height = 'auto';
        el.style.height = el.scrollHeight + 'px';
    }

    // --- 3. UI HELPERS ---

    function closeAllSidebars() {
        pnLeft.classList.remove('visivel');
        btnLeft.classList.remove('ativo');
        pnRight.classList.remove('visivel');
        btnRight.classList.remove('ativo');
        if(overlay) overlay.classList.remove('ativo');
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
            if(isMobile && overlay) overlay.classList.add('ativo');
        } else {
            panel.classList.remove('visivel');
            btn.classList.remove('ativo');
            if(isMobile) closeAllSidebars();
        }
    }

    function showSpecialistScreen(areaName) {
        welcomeTitle.textContent = `Olá, eu sou o especialista em ${areaName}.`;
        if(buttonsArea) buttonsArea.style.display = 'none';
        welcomeInput.focus();
        welcomeInput.placeholder = `Pergunte sobre ${areaName}...`;
    }

    function activateChat() {
        body.classList.remove('estado-inicial');
        chatContainer.style.display = 'flex';
    }

    // --- 4. FLUXO DE MENSAGEM ---

    function addMessage(role, text = '') {
        const isUser = role === 'user'; 
        const row = document.createElement('div');
        row.className = `chat-row ${isUser ? 'user' : 'bot'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `msg-bubble ${isUser ? 'usuario' : 'bot'}`;
        
        const content = document.createElement('div');
        content.className = 'conteudo-texto';
        
        if (!isUser) {
            content.innerHTML = renderMarkdownWithMath(text);
            triggerMathJax(content); // Renderiza matemática
        } else {
            content.textContent = text;
        }
        
        bubble.appendChild(content);
        row.appendChild(bubble);
        chatContainer.appendChild(row);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return row;
    }

    async function sendMessage(text) {
        text = text.trim();
        if (!text) return;

        welcomeInput.value = '';
        mainInput.value = '';
        autoResize(welcomeInput);
        autoResize(mainInput);

        activateChat();
        if (sourcesContent) sourcesContent.innerHTML = '<p class="vazio"><i class="fas fa-search"></i> Buscando referências...</p>';

        addMessage('user', text);
        if(mainBtn) mainBtn.disabled = true;

        const botRow = addMessage('ai', '<i class="fas fa-circle-notch fa-spin"></i> Processando...');
        const contentDiv = botRow.querySelector('.conteudo-texto');
        
        let fullText = ""; 

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: text })
            });

            if (!res.ok) throw new Error("Erro na rede");

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
                                fullText += json.content;
                                contentDiv.innerHTML = renderMarkdownWithMath(fullText);
                                // Renderiza MathJax em tempo real (essencial para Chrome)
                                triggerMathJax(contentDiv);
                            }
                            else if (json.type === 'sources' && json.content.length > 0) {
                                if (sourcesContent) {
                                    sourcesContent.innerHTML = '';
                                    json.content.forEach(src => {
                                        const [path, page] = src.split('|');
                                        const filename = path.split('/').pop();
                                        const item = document.createElement('div');
                                        item.className = 'source-chunk';
                                        item.innerHTML = `<strong><i class="far fa-file-pdf"></i> ${filename}</strong><p><a href="/pdfs/${path}" target="_blank" style="color:var(--accent)">Abrir PDF</a> (Pág. ${page})</p>`;
                                        sourcesContent.appendChild(item);
                                    });
                                    if (window.innerWidth > 1000 && !pnRight.classList.contains('visivel')) {
                                        toggleSidebar('right');
                                    }
                                }
                            }
                        } catch (e) {}
                    }
                }
            }
            if (sourcesContent && sourcesContent.innerHTML.includes('Buscando referências')) {
                sourcesContent.innerHTML = '<p class="vazio">Nenhuma citação exata encontrada.</p>';
            }
        } catch (e) {
            contentDiv.innerHTML = `<span style="color:red">Erro: ${e.message}</span>`;
        } finally {
            if(mainBtn) mainBtn.disabled = false;
            mainInput.focus();
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
        welcomeInput.addEventListener('input', function() { autoResize(this); });
    }
    if (mainInput) {
        mainInput.addEventListener('keydown', (e) => handleEnter(e, mainInput));
        mainInput.addEventListener('input', function() { autoResize(this); });
    }

    if (welcomeBtn) welcomeBtn.addEventListener('click', () => handleSendClick(welcomeInput));
    if (mainBtn) mainBtn.addEventListener('click', () => handleSendClick(mainInput));

    // UI Globais
    if(btnLeft) btnLeft.onclick = () => toggleSidebar('left');
    if(btnRight) btnRight.onclick = () => toggleSidebar('right');
    if(overlay) overlay.onclick = () => closeAllSidebars();
    document.querySelectorAll('.header-lateral').forEach(h => h.onclick = () => closeAllSidebars());
    
    // Swipe
    let touchStartX = 0;
    pnRight.addEventListener('touchstart', e => { touchStartX = e.changedTouches[0].screenX; }, {passive: true});
    pnRight.addEventListener('touchend', e => {
        if (e.changedTouches[0].screenX - touchStartX > 50 && pnRight.classList.contains('visivel')) toggleSidebar('right');
    }, {passive: true});

    // --- 6. INICIALIZAÇÃO ---
    async function init() {
        try {
            const res = await fetch('/knowledge-areas');
            const data = await res.json();
            
            if (sidebarList && data.areas) {
                sidebarList.innerHTML = '';
                if(data.areas.length === 0) sidebarList.innerHTML = '<div style="padding:15px;color:#aaa">Vazio</div>';
                
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
        } catch(e) {
            addMessage('ai', "Olá! Sou o UCDB-IA.");
        }

        document.querySelectorAll('.card-area').forEach(c => {
            c.onclick = () => showSpecialistScreen(c.getAttribute('data-area'));
        });
    }

    init();
});