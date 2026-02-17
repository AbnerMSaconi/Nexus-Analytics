// frontend/src/components/AdminPanel.tsx
import React, { useEffect, useState } from 'react';
import { Shield, Unlock, UserX, CheckCircle, AlertTriangle, Save, Trash2 } from 'lucide-react';
import { api } from '../assets/api';

// COMPONENTE INTERNO PARA A LINHA DA TABELA
const UserRow = ({ user, token, onUpdate }: { user: any, token: string, onUpdate: () => void }) => {
  const [selectedRole, setSelectedRole] = useState(user.role);
  const [saving, setSaving] = useState(false);

  // Função para salvar novo cargo
  const handleRoleChange = async () => {
    if (selectedRole === user.role) return;
    setSaving(true);
    try {
      await api.updateUserRole(user.id, selectedRole, token);
      onUpdate(); // Recarrega lista
    } catch (error) {
      alert("Erro ao atualizar cargo");
    } finally {
      setSaving(false);
    }
  };

  // Função para excluir usuário
  const handleDelete = async () => {
    const confirmMessage = `Tem certeza que deseja excluir permanentemente o usuário "${user.full_name}"?\n\nEssa ação não pode ser desfeita.`;
    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      await api.deleteUser(user.id, token);
      onUpdate(); // Atualiza a lista removendo a linha
    } catch (error: any) {
      alert(error.message || "Erro ao excluir usuário");
    }
  };

  return (
    <tr className="hover:bg-slate-800/30 transition-colors border-b border-slate-800/50 last:border-0">
      <td className="p-4">
        <div className="font-medium text-white">{user.full_name}</div>
        <div className="text-sm text-slate-500">{user.external_id}</div>
      </td>
      
      {/* Coluna de Cargo */}
      <td className="p-4">
        <div className="flex items-center gap-2">
          <select 
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-300 text-sm rounded p-1 focus:border-blue-500 outline-none cursor-pointer"
          >
            <option value="aluno">Aluno</option>
            <option value="professor">Professor</option>
            <option value="coordenador">Coordenador</option>
            <option value="administrador">Administrador</option>
          </select>
          
          {selectedRole !== user.role && (
            <button 
              onClick={handleRoleChange}
              disabled={saving}
              className="text-green-400 hover:text-green-300 transition-colors p-1"
              title="Salvar novo cargo"
            >
              <Save className="w-4 h-4" />
            </button>
          )}
        </div>
      </td>
      
      <td className="p-4 text-slate-400">{user.course || '-'}</td>
      
      {/* Coluna de Status */}
      <td className="p-4 text-center">
         {user.is_blocked ? (
            <div className="inline-flex items-center gap-1 text-red-400 bg-red-400/10 px-2 py-1 rounded text-xs font-bold border border-red-400/20">
              <UserX className="w-3 h-3" /> BLOQUEADO
            </div>
         ) : (
            <div className="inline-flex items-center gap-1 text-green-400 bg-green-400/10 px-2 py-1 rounded text-xs border border-green-400/20">
              <CheckCircle className="w-3 h-3" /> ATIVO
            </div>
         )}
         {user.failed_attempts > 0 && !user.is_blocked && (
            <div className="mt-1 text-[10px] text-yellow-500 flex justify-center items-center gap-1">
              <AlertTriangle className="w-3 h-3"/> {user.failed_attempts} falhas
            </div>
         )}
      </td>
      
      {/* Coluna de Ações */}
      <td className="p-4">
        <div className="flex items-center justify-end gap-3">
            {/* Botão de Desbloqueio (aparece apenas se bloqueado) */}
            {user.is_blocked && (
                <button
                    onClick={async () => {
                        try {
                            await api.unblockUser(user.id, token);
                            onUpdate();
                        } catch (e) { alert("Erro ao desbloquear"); }
                    }}
                    className="flex items-center gap-1 text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded transition-colors"
                    title="Desbloquear Usuário"
                >
                    <Unlock className="w-3 h-3" />
                    Desbloquear
                </button>
            )}

            {/* Botão de Excluir (Sempre visível) */}
            <button
                onClick={handleDelete}
                className="text-slate-500 hover:text-red-500 hover:bg-red-500/10 p-2 rounded-lg transition-all"
                title="Excluir Usuário permanentemente"
            >
                <Trash2 className="w-4 h-4" />
            </button>
        </div>
      </td>
    </tr>
  );
};

// COMPONENTE PRINCIPAL
export const AdminPanel: React.FC = () => {
  const [users, setUsers] = useState<any[]>([]);
  const token = localStorage.getItem('nexus_token') || '';

  const loadUsers = async () => {
    try {
        const data = await api.getUsers(token);
        setUsers(data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { loadUsers(); }, []);

  return (
    <div className="p-8 h-full overflow-y-auto bg-slate-950 text-white scrollbar-thin scrollbar-thumb-slate-800">
      <div className="flex items-center gap-3 mb-8">
        <div className="p-3 bg-red-500/10 rounded-xl border border-red-500/20">
            <Shield className="w-8 h-8 text-red-500" />
        </div>
        <div>
            <h1 className="text-2xl font-bold text-slate-100">Painel Administrativo</h1>
            <p className="text-slate-400 text-sm">Gerenciamento de usuários, permissões e segurança</p>
        </div>
      </div>
      
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-800/80 text-slate-400 text-xs font-bold uppercase tracking-wider border-b border-slate-700">
              <th className="p-4">Usuário</th>
              <th className="p-4">Função</th>
              <th className="p-4">Curso</th>
              <th className="p-4 text-center">Status</th>
              <th className="p-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {users.length > 0 ? (
                users.map((u) => (
                <UserRow key={u.id} user={u} token={token} onUpdate={loadUsers} />
                ))
            ) : (
                <tr>
                    <td colSpan={5} className="p-8 text-center text-slate-500 italic">
                        Nenhum usuário encontrado.
                    </td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};