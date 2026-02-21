// frontend/src/assets/api.ts
const API_URL = "http://localhost:8000";

export const api = {
  // Chat com streaming
  async chatStream(message: string, area: string, token: string | null) {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    return fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, area })
    });
  },

  async getHistory(token: string) {
    const res = await fetch(`${API_URL}/conversations`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },

  async getKnowledgeAreas() {
    const res = await fetch(`${API_URL}/knowledge-areas`);
    return res.json();
  },

  // --- NOVO MÉTODO PARA INGESTÃO ---
  async ingestDocuments(token: string) {
    const res = await fetch(`${API_URL}/ingest`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha na ingestão.');
    }
    return res.json();
  },
  
  async getUsers(token: string) {
    const res = await fetch(`http://localhost:8000/admin/users`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Falha ao buscar usuários');
    return res.json();
  },

    async unblockUser(userId: string, token: string) {
      const res = await fetch(`http://localhost:8000/admin/unblock/${userId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Falha ao desbloquear');
      return res.json();
    },
    async updateUserRole(userId: string, newRole: string, token: string) {
    const res = await fetch(`http://localhost:8000/admin/users/${userId}/role`, {
      method: 'PUT',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ role: newRole })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha ao atualizar cargo');
    }
    return res.json();
  },
  async deleteUser(userId: string, token: string) {
    const res = await fetch(`http://localhost:8000/admin/users/${userId}`, {
      method: 'DELETE',
      headers: { 
        'Authorization': `Bearer ${token}` 
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha ao excluir usuário');
    }
    return res.json();
  },
  async updateUserDetails(userId: string, data: any, token: string) {
    const res = await fetch(`http://localhost:8000/admin/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha ao atualizar cadastro do usuário');
    }
    return res.json();
  }
};
    
