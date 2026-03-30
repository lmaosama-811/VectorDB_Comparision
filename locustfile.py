"""
LOCUST LOAD TEST FILE - Vector DB Throughput & Concurrency Test
===============================================================
Purpose: Simulate N concurrent users sending queries to each Vector DB.
         Complements the Notebook (which measures Recall + single-query Latency).

METRICS LOCUST WILL MEASURE:
  - RPS (Requests Per Second): Number of queries processed per second
  - P50 / P95 / P99 Latency:  Latency distribution under concurrent load
  - Failure Rate:              Percentage of requests that timeout or error

HOW TO RUN (Terminal at D:\\Vector DB Comparison):
  1. Activate virtual environment:  .venv\\Scripts\\activate
  2. Run:  locust -f locustfile.py --class-picker
  3. Open browser:  http://localhost:8089
  4. Set Number of Users (e.g. 50) and Spawn Rate (e.g. 10), then click Start.

  Headless mode (no browser):
  locust -f locustfile.py --headless -u 50 -r 10 -t 60s --class-picker
  (-u = total users, -r = users added per second, -t = test duration)
"""

import random
import time
import os
import logging
from dotenv import load_dotenv
from locust import User, task, between, events

# Suppress noisy per-request HTTP logs from httpx (used by Weaviate & others)
# Without this, every single request prints "HTTP/1.1 200 OK" to the terminal
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load secrets (endpoints, API keys) from .env file
load_dotenv()

# ─────────────────────────────────────────
# SAMPLE QUERY VECTORS
# ─────────────────────────────────────────
# Pre-load 100 real embedding vectors from the saved .npy file.
# This avoids re-running the embedding model inside each request,
# which would skew latency measurements with model inference time.
import numpy as np
try:
    _all_vecs = np.load("msmarco_vectors_768.npy")   # Load embeddings saved from Notebook
    # _all_update_vecs = np.load("msmarco_vectors_768(2).npy")    # Use this for Index Construction Overhead test
    SAMPLE_VECS = _all_vecs[:100].tolist()            # Use only first 100 as a query pool
    # SAMPLE_VECS = (_all_update_vecs[:20] + _all_vecs[:80]).tolist() #     Use this for Index Construction Overhead test 
    print(f"Loaded {len(SAMPLE_VECS)} sample vectors from .npy file")
except FileNotFoundError:
    # Fallback: random vectors if file not found (results won't reflect real recall)
    SAMPLE_VECS = [np.random.rand(768).tolist() for _ in range(100)]
    print("WARNING: msmarco_vectors_768.npy not found. Using random vectors.")


def get_random_vec():
    """Pick a random vector from the pre-loaded sample pool for each request."""
    return random.choice(SAMPLE_VECS)


# ─────────────────────────────────────────
# HELPER: REPORT REQUEST RESULT TO LOCUST
# ─────────────────────────────────────────
def report(env, name, start, success=True, error=None):
    """
    Fire a Locust request event to record the result on the dashboard.

    Args:
        env:     Locust environment object (self.environment in User classes)
        name:    Label shown on the Locust dashboard (e.g. "Qdrant/Search")
        start:   Start timestamp from time.perf_counter()
        success: True if request succeeded, False on exception
        error:   Exception object if failed, None otherwise
    """
    elapsed_ms = (time.perf_counter() - start) * 1000  # Convert seconds → milliseconds
    env.events.request.fire(
        request_type="gRPC/HTTP",   # Display label for protocol type on dashboard
        name=name,
        response_time=elapsed_ms,
        response_length=0,          # We don't track payload size in this test
        exception=error,            # None = success; Exception object = failure
    )


# ═══════════════════════════════════════════════════════════════════
# USER CLASSES (one per Vector DB)
#
# Each class defines one type of virtual user.
# Locust spawns N instances of these classes concurrently.
# Use --class-picker flag to select which DB(s) to test at runtime.
# ═══════════════════════════════════════════════════════════════════

class QdrantUser(User):
    """
    Virtual user for Qdrant Cloud.
    Each instance maintains its own persistent connection to Qdrant.
    Tasks are picked randomly, weighted by the @task(weight) decorator.
    """
    wait_time = between(0.1, 0.5)   # Random pause between requests (seconds), simulates real user pacing

    def on_start(self):
        """Called once when each virtual user spawns. Initializes the DB connection."""
        from qdrant_client import QdrantClient
        self.client = QdrantClient(
            url=os.getenv("qdrant_endpoint"),
            api_key=os.getenv("qdrant_api_key"),
            timeout=10   # Fail fast after 10s so timeouts are captured as failures
        )

    @task(3)   # Default weight = 1; this task runs equally often with search_with_filter
    def search(self):
        """Plain vector search: no metadata filter applied."""
        vec = get_random_vec()
        start = time.perf_counter()   # Start timer immediately before the DB call
        try:
            self.client.query_points(
                collection_name="rag_test",
                query=vec,
                limit=10
            )
            report(self.environment, "Qdrant/Search", start)          # Record success
        except Exception as e:
            report(self.environment, "Qdrant/Search", start, error=e) # Record failure

    @task(1)
    def search_with_filter(self):
        """Filtered vector search: only return results where is_public == True."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        vec = get_random_vec()
        start = time.perf_counter()
        try:
            self.client.query_points(
                collection_name="rag_test",
                query=vec,
                limit=10,
                query_filter=Filter(must=[  # "must" = AND condition in Qdrant
                    FieldCondition(key="is_public", match=MatchValue(value=True))
                ])
            )
            report(self.environment, "Qdrant/Search+Filter", start)
        except Exception as e:
            report(self.environment, "Qdrant/Search+Filter", start, error=e)


class MilvusUser(User):
    """
    Virtual user for Milvus (Zilliz Cloud).

    Uses Milvus REST API v2 directly via `requests` instead of pymilvus.
    Reason: pymilvus uses gRPC at the transport layer, which blocks Locust's
    gevent event loop entirely — preventing ANY metrics from being recorded.
    Calling the REST endpoint bypasses gRPC and works correctly with gevent.
    """
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Set up REST session with auth headers (reused across requests)."""
        import requests
        self.session = requests.Session()
        # Zilliz Cloud REST API uses Bearer token for auth
        self.session.headers.update({
            "Authorization": f"Bearer {os.getenv('milvus_token')}",
            "Content-Type": "application/json"
        })
        # Build the search endpoint URL from the base URI
        base = os.getenv("milvus_endpoint").rstrip("/")
        self.search_url = f"{base}/v2/vectordb/entities/search"

    @task(3)
    def search(self):
        """Plain vector search via Milvus REST API v2."""
        vec = get_random_vec()
        payload = {
            "collectionName": "rag_test",
            "data": [vec],         # List of query vectors
            "limit": 10,
            "outputFields": ["id"] # Only return ID to minimize payload size
        }
        start = time.perf_counter()
        try:
            resp = self.session.post(self.search_url, json=payload, timeout=10)
            resp.raise_for_status()  # Raise on HTTP 4xx/5xx errors
            report(self.environment, "Milvus/Search", start)
        except Exception as e:
            report(self.environment, "Milvus/Search", start, error=e)

    @task(1)
    def search_with_filter(self):
        """Filtered vector search using Milvus filter expression via REST."""
        vec = get_random_vec()
        payload = {
            "collectionName": "rag_test",
            "data": [vec],
            "limit": 10,
            "outputFields": ["id"],
            "filter": "is_public == true"
            # "filter": "category == 'finance' and is_public == true"  #Use this for hard filter
        } # SQL-like filter expression
        start = time.perf_counter()
        try:
            resp = self.session.post(self.search_url, json=payload, timeout=10)
            resp.raise_for_status()
            report(self.environment, "Milvus/Search+Filter", start)
        except Exception as e:
            report(self.environment, "Milvus/Search+Filter", start, error=e)


class WeaviateUser(User):
    """
    Virtual user for Weaviate Cloud (REST API version).

    Uses direct GraphQL calls via `requests` instead of the v4 Client SDK.
    Reason: The v4 Client SDK uses gRPC/HTTP2 which blocks Locust's gevent loop,
    capping performance at ~13 RPS. Using `requests` allows true concurrency.
    """
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Set up REST session with Weaviate API Key."""
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {os.getenv('weaviate_api_key')}",
            "Content-Type": "application/json"
        })
        base = os.getenv("weaviate_endpoint").strip().rstrip("/")
        if not base.startswith("http"):
            base = f"https://{base}"
        self.graphql_url = f"{base}/v1/graphql"

    @task(3)
    def search(self):
        """Plain vector search via GraphQL."""
        vec = get_random_vec()
        query = {
            "query": """
            {
              Get {
                RagTest(
                  nearVector: { vector: %s }
                  limit: 10
                ) {
                  _additional { id }
                }
              }
            }
            """ % str(vec)
        }
        start = time.perf_counter()
        try:
            resp = self.session.post(self.graphql_url, json=query, timeout=10)
            resp.raise_for_status()
            report(self.environment, "Weaviate/Search", start)
        except Exception as e:
            report(self.environment, "Weaviate/Search", start, error=e)

    @task(1)
    def search_with_filter(self):
        """Filtered search (is_public == true) via GraphQL."""
        vec = get_random_vec()
        query = {
            "query": """
            {
              Get {
                RagTest(
                  nearVector: { vector: %s }
                  where: {
                    path: ["is_public"]
                    operator: Equal
                    valueBoolean: true
                  }
                  limit: 10
                ) {
                  _additional { id }
                }
              }
            }
            """ % str(vec)
        }
        start = time.perf_counter()
        try:
            resp = self.session.post(self.graphql_url, json=query, timeout=10)
            resp.raise_for_status()
            report(self.environment, "Weaviate/Search+Filter", start)
        except Exception as e:
            report(self.environment, "Weaviate/Search+Filter", start, error=e)


class PineconeUser(User):
    """Virtual user for Pinecone Serverless Cloud."""
    wait_time = between(0.1, 0.5)

    def on_start(self):
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("pinecone_api_key"))
        self.index = pc.Index("test")   # Connect to the "test" index; change name if different

    @task(3)
    def search(self):
        """Plain vector query. include_values=False reduces network payload."""
        vec = get_random_vec()
        start = time.perf_counter()
        try:
            self.index.query(
                vector=vec,
                top_k=10,
                include_values=False,    # Skip returning vector values (saves bandwidth)
                include_metadata=False   # Skip metadata (saves bandwidth, faster)
            )
            report(self.environment, "Pinecone/Search", start)
        except Exception as e:
            report(self.environment, "Pinecone/Search", start, error=e)

    @task(1)
    def search_with_filter(self):
        """Filtered search using Pinecone's MongoDB-style filter syntax."""
        vec = get_random_vec()
        start = time.perf_counter()
        try:
            self.index.query(
                vector=vec,
                top_k=10,
                include_values=False,
                include_metadata=False,
                filter={"is_public": {"$eq": True}}   # $eq operator = exact match
            )
            report(self.environment, "Pinecone/Search+Filter", start)
        except Exception as e:
            report(self.environment, "Pinecone/Search+Filter", start, error=e)


class ChromaUser(User):
    """Virtual user for ChromaDB Cloud."""
    wait_time = between(0.1, 0.5)

    def on_start(self):
        import chromadb
        self.client = chromadb.CloudClient(
            api_key=os.getenv("chroma_api_key"),
            tenant=os.getenv("chroma_tenant"),
            database="test"
        )
        self.collection = self.client.get_or_create_collection("RagTest")

    @task(3)
    def search(self):
        """Plain vector search. include=[] means return only IDs (no documents or embeddings)."""
        vec = get_random_vec()
        start = time.perf_counter()
        try:
            self.collection.query(query_embeddings=[vec], n_results=10, include=[])
            report(self.environment, "Chroma/Search", start)
        except Exception as e:
            report(self.environment, "Chroma/Search", start, error=e)

    @task(1)
    def search_with_filter(self):
        """Filtered search using Chroma's 'where' clause (MongoDB-style operators)."""
        vec = get_random_vec()
        start = time.perf_counter()
        try:
            self.collection.query(
                query_embeddings=[vec],
                n_results=10,
                include=[],
                where={"is_public": {"$eq": True}}   # 'where' = metadata filter in Chroma
            )
            report(self.environment, "Chroma/Search+Filter", start)
        except Exception as e:
            report(self.environment, "Chroma/Search+Filter", start, error=e)


# ═══════════════════════════════════════════════════════════════════
# STEP LOAD SHAPE (Optional: replaces manual user count on dashboard)
#
# Instead of setting a fixed number of users, this class automatically
# ramps users up in steps, letting you see the EXACT point at which
# latency starts climbing out of control (the "breaking point").
#
# HOW TO USE:
#   Simply run locust normally (with or without --class-picker).
#   Locust detects this class automatically and applies the ramp schedule.
#   NOTE: When this class is active, the "Number of users" field on the
#   web UI is IGNORED — the shape controls everything.
#
#   To disable it temporarily, comment out the entire class below.
# ═══════════════════════════════════════════════════════════════════

# from locust import LoadTestShape

# class StepLoadShape(LoadTestShape):
#     """
#     Gradually increases concurrent users in steps to find each DB's breaking point.
#     """

#     # Each tuple: (step_end_time_in_seconds, target_user_count, spawn_rate)
#     # spawn_rate = how many new users are added per second at each step transition
#     steps = [
#         (2*60,  10,   5),   
#         (4*60,  25,   5),   
#         (6*60,  50,  10),   
#         (8*60,  100,  10),  
#         (10*60, 200, 10),
#         (12*60, 300, 10),
#         (14*60, 400, 10),
#         (16*60, 500, 10),
#     ]

#     def tick(self):
#         """
#         Called by Locust every second to determine how many users should be active.
#         Returns (user_count, spawn_rate) tuple, or None to stop the test.
#         """
#         run_time = self.get_run_time()   # Seconds elapsed since test started

#         for step_end, user_count, spawn_rate in self.steps:
#             if run_time < step_end:
#                 # Still within this step's time window -> maintain its user count
#                 return (user_count, spawn_rate)

#         return None   # All steps finished -> Locust stops the test automatically
