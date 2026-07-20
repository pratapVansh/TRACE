import asyncio
import uuid
import sys
from app.db.session import async_session_factory
from app.repositories.conversation_repository import ConversationRepository
from app.agents.framework.memory.conversation_memory import ConversationMemory
from app.agents.framework.memory.manager import MemoryManager

async def test_fk_violation():
    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        memory = ConversationMemory(repo)
        
        # We need a valid user_id
        # Get one from DB
        from sqlalchemy import text
        res = await session.execute(text("SELECT id FROM users LIMIT 1"))
        user_id_row = res.fetchone()
        if not user_id_row:
            print("No users found to test with.")
            return
            
        user_id = user_id_row[0]
        
        manager = MemoryManager(conversation_memory=memory)
        
        # Simulate frontend generating a random UUID
        new_conv_id = uuid.uuid4()
        
        # 1. Load conversation (will set _conversation_id and realize it doesn't exist)
        await manager.load_conversation(conversation_id=new_conv_id, user_id=user_id)
        
        # 2. Append message (simulating save_conversation_turn)
        # Should now get-or-create correctly
        try:
            await manager.save_conversation_turn("user", "Hello world")
            print("FK Violation Fixed! Conversation auto-created successfully.")
        except Exception as e:
            print(f"FAILED: {type(e).__name__} - {e}")
            raise
            
        # 3. Simulate parallel execution appending simultaneously
        # Call append again, it shouldn't crash
        try:
            await manager.save_conversation_turn("assistant", "Hi there")
            print("Sequential append successful.")
        except Exception as e:
            print(f"FAILED: {type(e).__name__} - {e}")
            raise
            
if __name__ == "__main__":
    asyncio.run(test_fk_violation())
