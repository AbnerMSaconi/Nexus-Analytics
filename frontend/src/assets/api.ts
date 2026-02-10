// frontend/src/api.ts
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
  }
};