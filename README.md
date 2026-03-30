# VectorDB_Comparision
**A benchmark experiment to verify Vector Database Cababilities.**

I run this project to examine by myself potentials of 5 latest and most prevalent vector database systems: Chroma, Qdrant, Weaviate, Milvus (Zilliz) and Pinecone. In this experiment, all these vector databases are run on cloud to maintain the same test condition between them. 

## Overview
I have prompted Gemini (in deep research mode) to generate a detaild report comparing these 5 vector databases with specific statistics about their performance.  
In this project, I will examine whether these figures are correct or not. I have measures these quantities in my project:
+ Recall@10 and Latency when 100 users send request respectively with diverse kind of query:
  + Query without filter
  + Query with filter (Simple - High constrained metadata)
+ Stress load parameters when number of users increases gradually to  users: QPS, Failure percentage,...
+ Scalability when ingesting 10,000 vectors 
+ Data visibility latency
+ Index Construction Overhead

The result of some measures is shown in these below table (check REPORT.md for more detail):  
|             | Without filter    | With filter (simple) |  With filter(hard)|  
|             | Recall  | Latency | Recall  |  Latency   | Recall | Latency  |  
| Qdrant      | 99.78%  | 0.28    | 98.14%  |  0.28      | 100.00%| 0.28     | 
| Pinecone    | 99.04%  | 0.27    | 98.87%  |  0.27      | 99.16% | 0.25     | 
| Milvus      | 95.49%  | 0.25    | 95.6%   |  0.26      | 21.25% | 0.26     | 
| Weaviate    | 99.73%  | 0.1     | 100.00% |  0.1       | 100.00%| 0.1      | 
| Chroma      | 98.67%  | 0.26    | 98.24%  |  0.25      | 97.14% | 0.25     | 

**Note**: The data is reference only. The results vary depending on several factors, include: hardcore system, quality of internet connection to cloud,...

## Conclude
Each vector database has their own strength. Based on different purposes, we utilize their strenghth:
+ Milvus:
+ Qdrant:
+ Pinecone:
+ Chroma:
+ Weaviate: 
