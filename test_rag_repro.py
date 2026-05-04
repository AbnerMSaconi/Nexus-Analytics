import asyncio
import os
from app.core.rag import get_rag_chain_async
from app.core.config import settings

async def test_rag():
    print("Testing RAG for area 'direito'...")
    chain = await get_rag_chain_async("direito")
    if not chain:
        print("Chain not found!")
        return
    
    question = "O que é o Princípio da Supremacia da Constituição?"
    print(f"Question: {question}")
    
    result = await chain.ainvoke({"question": question, "chat_history": []})
    
    print("\n--- ANSWER ---")
    print(result["answer"])
    print("\n--- SOURCES ---")
    for doc in result["source_documents"]:
        print(f"- {doc.metadata.get('source')} (Topic: {doc.metadata.get('topic')})")
        # print(f"  Content: {doc.page_content[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_rag())
