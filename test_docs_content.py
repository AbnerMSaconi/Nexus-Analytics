import asyncio
import os
from app.core.rag import get_rag_chain_async
from app.core.config import settings

async def test_docs():
    chain = await get_rag_chain_async("direito")
    # Get the docs directly from the first part of the chain
    # The chain structure: RunnableParallel({...})
    # We can just call the retriever part
    emb_model = (await chain.ainvoke({"question": "Supremacia", "chat_history": []}))
    docs = emb_model["source_documents"]
    print(f"Found {len(docs)} docs")
    if docs:
        print(f"Sample content: {docs[0].page_content[:300]}")

if __name__ == "__main__":
    asyncio.run(test_docs())
