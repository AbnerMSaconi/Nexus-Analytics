from typing import List, Dict, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Mapeia user_id para uma lista de conexões ativas
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        count = sum(len(websockets) for websockets in self.active_connections.values())
        logger.info(f"🔌 Novo WS: User={user_id}. Total de conexões: {count}")
        
        await self.broadcast_online_count()

    async def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        count = sum(len(websockets) for websockets in self.active_connections.values())
        logger.info(f"❌ WS Fechado: User={user_id}. Restam {count} conexões.")
                
        await self.broadcast_online_count()

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception:
                    pass

    async def broadcast_online_count(self):
        # Conta o número de usuários ÚNICOS online
        # (Se um usuário tiver 3 abas abertas, ele conta como 1 usuário online)
        count = len(self.active_connections)
        logger.info(f"📢 Transmitindo contagem de usuários únicos online: {count}")
        message = {"type": "online_count", "count": count}
        await self.broadcast(message)

    async def broadcast(self, message: dict):
        to_remove = []
        payload = json.dumps(message)
        
        # Iterar sobre uma cópia dos itens para evitar RuntimeError se a lista mudar durante o loop
        for user_id, websockets in list(self.active_connections.items()):
            disconnected_from_user = []
            # Também iterar sobre uma cópia do set de websockets
            for websocket in list(websockets):
                try:
                    await websocket.send_text(payload)
                except Exception as e:
                    logger.error(f"❌ Falha ao enviar broadcast para {user_id}: {e}")
                    disconnected_from_user.append(websocket)
            
            for ws in disconnected_from_user:
                if ws in websockets:
                    websockets.remove(ws)
            
            if not websockets:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            if user_id in self.active_connections:
                del self.active_connections[user_id]

manager = ConnectionManager()
