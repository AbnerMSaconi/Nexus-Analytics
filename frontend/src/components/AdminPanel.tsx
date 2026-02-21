// frontend/src/components/AdminPanel.tsx
import React, { useEffect, useState } from 'react';
// Importe o ícone Edit e X (para fechar o modal)
import { Shield, Unlock, UserX, CheckCircle, AlertTriangle, Save, Trash2, Edit, X } from 'lucide-react';
import { api } from '../assets/api';

// COMPONENTE INTERNO PARA A LINHA DA TABELA
const UserRow = ({ user, token, onUpdate, onEditClick }: { user: any, token: string, onUpdate: () => void, onEditClick: (u: any) => void }) => {
  const [selectedRole, setSelectedRole] = useState(user.role);
  const [saving, setSaving] = useState(false);

  const handleRoleChange = async () => {
    if (selectedRole === user.role) return;
    setSaving(true);
    try {
      await api.updateUserRole(user.id, selectedRole, token);
      onUpdate();
    } catch (error) {
      alert("Erro ao atualizar cargo");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Tem certeza que deseja excluir permanentemente o usuário "${user.full_name}"?\n\nEssa ação não pode ser desfeita.`)) {
      return;
    }
    try {
      await api.deleteUser(user.id, token);
      onUpdate();
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
            <button onClick={handleRoleChange} disabled={saving} className="text-green-400 hover:text-green-300 p-1" title="Salvar cargo">
              <Save className="w-4 h-4" />
            </button>
          )}
        </div>
      </td>
      
      <td className="p-4 text-slate-400">{user.course || '-'}</td>
      
      <td className="p-4 text-center">
         {user.is_blocked ? (
            <div className="inline-flex items-center gap-1 text-red-400 bg-red-400/10 px-2 py-1 rounded text-xs font-bold border border-red-400/20">
              <UserX className="w-3 h-3" /> BLOQ
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
      
      <td className="p-4">
        <div className="flex items-center justify-end gap-2">
            {user.is_blocked && (
                <button onClick={async () => { await api.unblockUser(user.id, token); onUpdate(); }} className="flex items-center text-xs bg-red-600 hover:bg-red-500 text-white px-2 py-1.5 rounded transition-colors" title="Desbloquear">
                    <Unlock className="w-3 h-3" />
                </button>
            )}

            {/* --- BOTÃO DE EDITAR --- */}
            <button
                onClick={() => onEditClick(user)}
                className="text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 p-2 rounded-lg transition-all"
                title="Editar Cadastro"
            >
                <Edit className="w-4 h-4" />
            </button>

            {/* --- BOTÃO DE EXCLUIR --- */}
            <button
                onClick={handleDelete}
                className="text-slate-400 hover:text-red-500 hover:bg-red-500/10 p-2 rounded-lg transition-all"
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
  const [editingUser, setEditingUser] = useState<any>(null); // Estado para controlar o modal de edição
  const [formData, setFormData] = useState({ full_name: '', external_id: '', role: '', course: '', password: '' });
  const [loadingForm, setLoadingForm] = useState(false);

  const token = localStorage.getItem('nexus_token') || '';

  const loadUsers = async () => {
    try {
        const data = await api.getUsers(token);
        setUsers(data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { loadUsers(); }, []);

  // Abre o modal preenchendo os dados do usuário
  const handleOpenEdit = (user: any) => {
    setFormData({
      full_name: user.full_name || '',
      external_id: user.external_id || '',
      role: user.role || 'aluno',
      course: user.course || '',
      password: '' // Senha começa vazia
    });
    setEditingUser(user);
  };

  // Envia os dados atualizados para o backend
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoadingForm(true);
    
    try {
      // Monta os dados, ignorando a senha se ela estiver em branco
      const dataToUpdate: any = { ...formData };
      if (!dataToUpdate.password) {
        delete dataToUpdate.password;
      }

      await api.updateUserDetails(editingUser.id, dataToUpdate, token);
      alert("Usuário atualizado com sucesso!");
      setEditingUser(null); // Fecha o modal
      loadUsers(); // Recarrega a tabela
    } catch (error: any) {
      alert(error.message || "Erro ao atualizar usuário");
    } finally {
      setLoadingForm(false);
    }
  };

  return (
    <div className="p-8 h-full overflow-y-auto bg-slate-950 text-white relative">
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
                <UserRow key={u.id} user={u} token={token} onUpdate={loadUsers} onEditClick={handleOpenEdit} />
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

      {/* --- MODAL DE EDIÇÃO --- */}
      {editingUser && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-800 bg-slate-800/50">
              <h2 className="text-lg font-bold">Editar Cadastro</h2>
              <button onClick={() => setEditingUser(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Nome Completo</label>
                <input 
                  type="text" 
                  value={formData.full_name} 
                  onChange={e => setFormData({...formData, full_name: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 outline-none focus:border-blue-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">ID (Login/Email)</label>
                <input 
                  type="text" 
                  value={formData.external_id} 
                  onChange={e => setFormData({...formData, external_id: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 outline-none focus:border-blue-500 text-white"
                />
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm text-slate-400 mb-1">Cargo</label>
                  <select 
                    value={formData.role} 
                    onChange={e => setFormData({...formData, role: e.target.value})}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 outline-none focus:border-blue-500 text-white"
                  >
                    <option value="aluno">Aluno</option>
                    <option value="professor">Professor</option>
                    <option value="coordenador">Coordenador</option>
                    <option value="administrador">Administrador</option>
                  </select>
                </div>
                
                <div className="flex-1">
                  <label className="block text-sm text-slate-400 mb-1">Curso</label>
                  <input 
                    type="text" 
                    value={formData.course} 
                    onChange={e => setFormData({...formData, course: e.target.value})}
                    placeholder="Ex: Direito"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 outline-none focus:border-blue-500 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">Nova Senha (opcional)</label>
                <input 
                  type="password" 
                  value={formData.password} 
                  onChange={e => setFormData({...formData, password: e.target.value})}
                  placeholder="Preencha apenas se quiser resetar a senha"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 outline-none focus:border-blue-500 text-white placeholder-slate-600"
                />
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button type="button" onClick={() => setEditingUser(null)} className="px-4 py-2 text-slate-400 hover:text-white transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={loadingForm} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2">
                  {loadingForm ? 'Salvando...' : 'Salvar Alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};