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
| Database | Recall (No Filter) | Latency (No Filter) | Recall (Simple Filter) | Latency (Simple Filter) | Recall (Hard Filter) | Latency (Hard Filter) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Weaviate** | 99.73% | 0.10s | 100.00% | 0.10s | 100.00% | 0.10s |
| **Qdrant** | 99.78% | 0.28s | 98.14% | 0.28s | 100.00% | 0.28s |
| **Pinecone** | 99.04% | 0.27s | 98.87% | 0.27s | 99.16% | 0.25s |
| **Chroma** | 98.67% | 0.26s | 98.24% | 0.25s | 97.14% | 0.25s |
| **Milvus** | 95.49% | 0.25s | 95.60% | 0.26s | 21.25% | 0.26s |

**Note**: The data is reference only. The results vary depending on several factors, include: hardcore system, quality of internet connection to cloud,...

## Conclude
Each database excels in specific scenarios. Depending on your project's priorities, here is how to choose:

* **Weaviate:** The top performer for **speed and precision**. Ideal for RAG applications requiring sub-100ms latency and complex filtering.
* **Qdrant:** The most **stable and resource-efficient** choice. Perfect for production environments where Rust-based reliability and balanced performance are key.
* **Pinecone:** The ultimate **No-Ops** solution. Best for teams wanting to scale instantly without managing any underlying infrastructure.
* **Chroma:** The go-to for **simplicity and rapid prototyping**. Excellent for lightweight projects and a smooth developer experience.
* **Milvus (Zilliz):** An **enterprise-grade powerhouse** designed for massive scalability (billion-scale vectors), suitable for large data lakes with specialized tuning.
