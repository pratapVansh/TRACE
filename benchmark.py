import asyncio
import time
import os
import sys

# Ensure backend app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.graph.neo4j_graph_store import Neo4jGraphStore
from app.services.vector_store import QdrantVectorStore

async def run_benchmark():
    print("--- BENCHMARK START ---")
    
    from app.services.embedding_service import _encode_batch_async
    start_time = time.time()
    for _ in range(10):
        # We will embed the same text repeatedly to check cache effectiveness
        await _encode_batch_async(["This is a test sentence for benchmarking."])
    embed_latency = time.time() - start_time
    print(f"Embedding Latency (10 calls): {embed_latency:.4f}s")
    
    # 2. Neo4j benchmark
    neo4j_store = Neo4jGraphStore()
    neo4j_latency = 0
    if settings.neo4j_uri:
        await neo4j_store.connect()
        start_time = time.time()
        for _ in range(10):
            # Just a simple cypher query that might be optimized
            await neo4j_store._driver.execute_query("MATCH (n) RETURN count(n) LIMIT 1")
        neo4j_latency = time.time() - start_time
        await neo4j_store.close()
        print(f"Neo4j Latency (10 calls): {neo4j_latency:.4f}s")
    
    # 3. Qdrant benchmark
    qdrant_store = QdrantVectorStore()
    qdrant_latency = 0
    if settings.qdrant_url:
        await qdrant_store.connect()
        start_time = time.time()
        for _ in range(10):
            await qdrant_store.search([0.1]*384, top_k=5)
        qdrant_latency = time.time() - start_time
        print(f"Qdrant Latency (10 calls): {qdrant_latency:.4f}s")
        
    print("--- BENCHMARK END ---")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
