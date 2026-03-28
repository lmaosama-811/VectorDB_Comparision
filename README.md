# VectorDB_Comparision
**A benchmark experiment to verify Vector Database Cababilities.**

I run this project to examine by myself potentials of 5 latest and most prevalent vector database systems: Chroma, Qdrant, Weaviate, Milvus (Zilliz) and Pinecone. In this experiment, all these vector databases are run on cloud to maintain the same test condition between them. 

## Overview
I have prompted Gemini (in deep research mode) to generate a detaild report comparing these 5 vector databases with specific statistics about their performance.  
In this project, I will examine whether these figures are correct or not. I have measures these quantities in my project:
+ Recall@10 and Latency when 100 users send request respectively with diverse kind of query:
  + Query without filter
  + Query with filter (Simple - High constrained metadata)
+ Stress load parameters when number of users increases gradually to 100 users: QPS, Failure percentage,...
+ Scalability when ingest 10,000 vectors 
