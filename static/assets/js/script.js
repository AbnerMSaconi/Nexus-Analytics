// static/assets/js/script.js - Versão Final Nexus
document.addEventListener('DOMContentLoaded', () => {
    // Inicializa ícones Lucide
    lucide.createIcons();

    // --- ESTADO & REFERÊNCIAS ---
    const state = {
        token: localStorage.getItem('nexus_token'),
        area: 'Geral',
        user: null
    };

    const el = {
        navChat: document.getElementById('nav-chat'),
        navDocs: document.getElementById('nav-docs'),
        navLogin: document.getElementById('nav-login'),
        navLogout: document.getElementById('nav-logout'),
        
        viewHistory: document.getElementById('view-history'),
        viewDocs: document.getElementById('view-docs'),
        
        welcomeScreen: document.getElementById('welcome-screen'),
        chatContainer: document.getElementById('chat-container'),
        messagesArea: document.getElementById('messages-area'),
        chatInput: document.getElementById('chat-input'),
        btnSend: document.getElementById('btn-send'),
        chatHeader: document.getElementById('chat-header'),
        chatTitle: document.getElementById('chat-title'),
        
        modalAuth: document.getElementById('modal-auth'),
        formAuth: document.getElementById('form-auth'),
        authTitle: document.getElementById('auth-title'),
        btnToggleAuth: document.getElementById('btn-toggle-auth'),
        btnCloseModal: document.getElementById('btn-close-modal'),
        
        listHistory: document.getElementById('list-history'),
        listDocs: document.getElementById('list-docs'),
        btnNewChat: document.getElementById('btn-new-chat')
    };

    // --- 1. NAVEGAÇÃO & UI ---
    function switchTab(tab) {
        el.navChat.classList.remove('active');
        el.navDocs.classList.remove('active');
        el.viewHistory.classList.add('hidden');
        el.viewDocs.classList.add('hidden');

        if (tab === 'chat') {
            el.navChat.classList.add('active');
            el.viewHistory.classList.remove('hidden');
        } else {
            el.navDocs.classList.add('active');
            el.viewDocs.classList.remove('hidden');
            loadDocs();
        }
    }

    el.navChat.onclick = () => switchTab('chat');
    el.navDocs.onclick = () => switchTab('docs');
    
    el.btnNewChat.onclick = () => {
        el.messagesArea.innerHTML = '';
        el.messagesArea.classList.add('hidden');
        el.welcomeScreen.classList.remove('hidden');
        el.chatHeader.classList.add('hidden');
        state.area = 'Geral';
        updateAreaSelection();
    };

    // --- 2. AUTENTICAÇÃO ---
    function updateAuthState() {
        if (state.token) {
            el.navLogin.classList.add('hidden');
            el.navLogout.classList.remove('hidden');
            loadHistory();
        } else {
            el.navLogin.classList.remove('hidden');
            el.navLogout.classList.add('hidden');
            el.listHistory.innerHTML = '<div class="p-4 text-center"><i data-lucide="lock" class="mx-auto w-6 h-6 text-slate-600 mb-2"></i><p class="text-xs text-slate-500">Faça login para salvar seu histórico.</p></div>';
            lucide.createIcons();
        }
    }

    el.navLogin.onclick = () => el.modalAuth.classList.remove('hidden');
    el.btnCloseModal.onclick = () => el.modalAuth.classList.add('hidden');
    
    el.navLogout.onclick = () => {
        if(confirm("Deseja desconectar?")) {
            localStorage.removeItem('nexus_token');
            state.token = null;
            updateAuthState();
            location.reload();
        }
    };

    el.formAuth.onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById('auth-id').value;
        const pass = document.getElementById('auth-pass').value;
        const name = document.getElementById('auth-name').value;
        const isSignup = !document.getElementById('field-name').classList.contains('hidden');
        const btnText = document.getElementById('btn-auth-text');

        btnText.innerText = "Processando...";
        
        try {
            const res = await fetch(isSignup ? '/signup' : '/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ external_id: id, password: pass, full_name: name })
            });
            const data = await res.json();
            
            if (res.ok) {
                state.token = data.access_token;
                localStorage.setItem('nexus_token', data.access_token);
                el.modalAuth.classList.add('hidden');
                updateAuthState();
                alert(`Bem-vindo, ${id}!`);
            } else {
                alert(data.detail || "Falha na autenticação");
            }
        } catch (err) { alert("Erro de conexão"); }
        finally { btnText.innerText = isSignup ? "Cadastrar" : "Entrar no Sistema"; }
    };

    el.btnToggleAuth.onclick = (e) => {
        e.preventDefault();
        const fieldName = document.getElementById('field-name');
        fieldName.classList.toggle('hidden');
        const isSignup = !fieldName.classList.contains('hidden');
        el.authTitle.innerText = isSignup ? "Criar Nova Conta" : "Acesso Corporativo";
        el.btnToggleAuth.innerText = isSignup ? "Já tenho conta" : "Criar nova conta";
        document.getElementById('btn-auth-text').innerText = isSignup ? "Cadastrar" : "Entrar no Sistema";
    };

    // --- 3. LÓGICA DO CHAT ---
    function updateAreaSelection() {
        document.querySelectorAll('.card-area').forEach(btn => {
            if (btn.dataset.area === state.area) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
    }

    document.querySelectorAll('.card-area').forEach(btn => {
        btn.onclick = () => {
            state.area = btn.dataset.area;
            updateAreaSelection();
        };
    });

    async function sendMessage() {
        const text = el.chatInput.value.trim();
        if (!text) return;

        // UI Updates
        el.welcomeScreen.classList.add('hidden');
        el.messagesArea.classList.remove('hidden');
        el.chatHeader.classList.remove('hidden');
        el.chatTitle.innerText = state.area; // Atualiza título
        el.chatInput.value = '';
        
        appendMessage('user', text);
        const botBubble = appendMessage('ai', '<div class="flex items-center gap-2"><span class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></span><span class="text-xs text-slate-400">Analisando documentos...</span></div>');

        try {
            const headers = { 'Content-Type': 'application/json' };
            if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

            const res = await fetch('/chat', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ message: text, area: state.area })
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";
            let citations = [];
            let isFirstChunk = true;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.type === 'chunk') {
                                if (isFirstChunk) { botBubble.innerHTML = ''; isFirstChunk = false; }
                                fullText += data.content;
                                botBubble.innerHTML = marked.parse(fullText);
                                el.chatContainer.scrollTop = el.chatContainer.scrollHeight;
                            } else if (data.type === 'sources') {
                                citations = data.content;
                            }
                        } catch (e) {}
                    }
                }
            }

            // Append citations
            if (citations.length > 0) {
                const citeHTML = citations.map(c => `
                    <div class="citation-item">
                        <i data-lucide="file-text" class="w-3 h-3 inline mr-2 text-blue-400"></i>${c}
                    </div>`
                ).join('');
                botBubble.innerHTML += `
                    <div class="citation-block">
                        <div class="citation-header"><i data-lucide="book-open" class="w-3 h-3"></i> FONTES UTILIZADAS</div>
                        ${citeHTML}
                    </div>`;
                lucide.createIcons();
            }
            
            // Re-render MathJax
            if(window.MathJax) window.MathJax.typesetPromise([botBubble]);

            if (state.token) loadHistory(); 

        } catch (e) {
            botBubble.innerHTML = "<span class='text-red-400'>Erro de conexão com o servidor RAG.</span>";
        }
    }

    function appendMessage(role, html) {
        const div = document.createElement('div');
        div.className = `msg-row ${role}`;
        div.innerHTML = `
            ${role === 'ai' ? '<div class="msg-avatar ai"><i data-lucide="bot"></i></div>' : ''}
            <div class="msg-bubble">${html}</div>
            ${role === 'user' ? '<div class="msg-avatar user"><i data-lucide="user"></i></div>' : ''}
        `;
        el.messagesArea.appendChild(div);
        el.chatContainer.scrollTop = el.chatContainer.scrollHeight;
        lucide.createIcons();
        return div.querySelector('.msg-bubble');
    }

    // --- 4. DADOS ---
    async function loadHistory() {
        if (!state.token) return;
        try {
            const res = await fetch('/conversations', { headers: { 'Authorization': `Bearer ${state.token}` } });
            if (res.status === 401) { 
                localStorage.removeItem('nexus_token'); 
                state.token = null;
                updateAuthState();
                return; 
            }
            const data = await res.json();
            el.listHistory.innerHTML = data.map(c => `
                <div class="p-3 mx-2 mb-1 hover:bg-slate-800 rounded-lg cursor-pointer transition-colors group">
                    <div class="font-medium text-slate-300 text-sm truncate group-hover:text-white">${c.title || 'Nova Conversa'}</div>
                    <div class="text-[10px] text-slate-600 flex items-center gap-1 mt-1">
                        <i data-lucide="clock" class="w-3 h-3"></i> ${new Date(c.updated_at).toLocaleDateString()}
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        } catch (e) {}
    }

    async function loadDocs() {
        el.listDocs.innerHTML = '<div class="text-center mt-4"><span class="w-4 h-4 border-2 border-blue-500 rounded-full animate-spin inline-block"></span></div>';
        try {
            const res = await fetch('/knowledge-areas');
            const data = await res.json();
            
            if (data.areas.length === 0) {
                el.listDocs.innerHTML = '<p class="text-xs text-slate-500 text-center mt-4">Nenhuma área indexada.</p>';
                return;
            }

            el.listDocs.innerHTML = data.areas.map(area => `
                <div class="bg-slate-800/50 p-3 rounded-xl mb-3 border border-slate-800 hover:border-slate-700 transition-colors">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 bg-slate-800 rounded-lg flex items-center justify-center text-yellow-500">
                            <i data-lucide="folder"></i>
                        </div>
                        <div>
                            <div class="font-medium text-slate-200 text-sm">${area}</div>
                            <div class="text-[10px] text-slate-500">Índice Vetorial Disponível</div>
                        </div>
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        } catch (e) {
            el.listDocs.innerHTML = '<p class="text-xs text-red-400 text-center">Erro ao carregar docs.</p>';
        }
    }

    // Inicialização
    el.btnSend.onclick = sendMessage;
    el.chatInput.onkeydown = (e) => { if(e.key === 'Enter') sendMessage(); };
    updateAuthState();
});