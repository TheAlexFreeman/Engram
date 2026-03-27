---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: databases-and-vector-stores-research
phase: orientation
---

# Databases & Vector Stores Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `software-engineering/databases/` subdomain that fills the zero-file gap in database systems beyond PostgreSQL-in-Django.

## Existing coverage audit

### What already touches databases

1. **RAG architecture** (`ai/frontier/retrieval-memory/rag-architecture.md`): describes dense retrieval, BM25, reranking, and chunking strategies — all of which assume a vector store underneath, but the vector store itself is treated as a black box. The databases/ ANN-algorithms and vector-landscape files should be the referent that grounds these assumptions.

2. **Persistent memory architectures** (`ai/frontier/retrieval-memory/persistent-memory-architectures.md`): explicitly discusses the weaknesses of vector-store memory (no update semantics, no trust tracking, no schema) and the strengths of knowledge-graph memory (typed relations, contradiction detection, SPARQL queries). This is the strongest existing motivation for a systematic databases/ treatment.

3. **Content-addressable storage** (`software-engineering/systems-architecture/content-addressable-storage-and-integrity.md`): covers CAS/Merkle structures (git, Nix) at the systems-architecture level. The databases/ files should build on this by covering WAL, append-only logs, and B-tree internals where relevant — but should not re-explain CAS.

4. **Redis internals** (`software-engineering/devops/redis-internals-and-operations.md`): covers Redis data structures, persistence modes, memory management, eviction policies, replication, and monitoring. Comprehensive treatment focused on operations. The databases/ Redis-as-database-paradigm file should cross-reference this but focus on data-modeling patterns and use-case selection, not re-explain ops.

5. **Django ORM / PostgreSQL files** (`software-engineering/django/django-orm-postgres.md`, `psycopg3-and-connection-management.md`, `django-database-pooling.md`): cover PostgreSQL through the Django lens. The databases/ files should cover database concepts at the systems level, not through a framework lens.

6. **Agentic RAG patterns** (`ai/frontier/retrieval-memory/agentic-rag-patterns.md`): treats Chroma, Pinecone, and Weaviate as established technology for agentic retrieval. The vector-database-landscape file should be the primer this file assumes.

### What does NOT already exist

- No file on ANN index algorithms (HNSW, IVF, LSH)
- No file comparing vector databases (Pinecone, Weaviate, Chroma, Qdrant, pgvector)
- No file on hybrid search (sparse + dense fusion)
- No file on graph databases (Neo4j, property graphs)
- No file on document stores (MongoDB)
- No file on RDF / SPARQL / knowledge graphs (as database technology)
- No file on polyglot persistence or database selection frameworks
- No SQL fundamentals file (Django ORM coverage assumes PostgreSQL context)

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| databases/ vs. ai/retrieval-memory/ | AI/retrieval-memory describes what RAG systems do and why. Databases/ describes how the underlying storage/retrieval engines work internally. | RAG files are consumers; database files explain the infrastructure. |
| databases/ vs. devops/redis | Redis-internals covers operations (persistence, eviction, replication, monitoring). Databases/ covers Redis data-structure patterns and use-case selection. | Ops vs. data-modeling split. Cross-reference rather than duplicate. |
| databases/ vs. django/ | Django ORM files are framework-specific. Databases/ covers database concepts at the systems level. | Framework-agnostic coverage complements the existing Django-specific files. |
| databases/ vs. systems-architecture/ | Systems-architecture covers CAS, Merkle trees, concurrency models. Databases/ covers specific database engines and their indexing/query strategies. | The systems-architecture files are the theoretical foundation; databases/ files are the applied layer. |
| ANN algorithms vs. vector database landscape | ANN-algorithms is the CS/algorithms treatment (HNSW, IVF, LSH — how they work). Vector-database-landscape is the product comparison (Pinecone, Weaviate, etc. — what to choose). | Theory vs. practice split keeps the algorithm file durable as products change. |

## Target file list (9 files + synthesis)

### Phase 2: Vector Databases (3 files)

1. **ann-index-algorithms-hnsw-ivf-lsh.md**
   The approximate nearest-neighbor search problem: why exact kNN is O(nd) and infeasible at scale. Three major index families: HNSW (hierarchical navigable small-world graphs — skip-list-inspired layered graph; insert/search algorithms; ef_construction, M, ef_search tuning parameters; recall-speed tradeoff curve). IVF (inverted file index — k-means quantization of embedding space into Voronoi cells; nprobe tuning; IVF-PQ for memory compression). LSH (locality-sensitive hashing — random projection hash families; AND/OR constructions; false positive/negative rate control). ANN-benchmarks.com methodology and the recall-latency Pareto frontier. This is the theory file that the vector-database product file depends on.

2. **vector-database-landscape-pinecone-weaviate-chroma.md**
   The managed/open-source spectrum. Pinecone: serverless, namespaces, metadata filtering, sparse+dense hybrid, pod-based vs. serverless pricing. Weaviate: open-source, GraphQL API, modules (text2vec, img2vec, generative), multi-tenancy, Kubernetes deployment. Chroma: embedded-first Python-native, SQLite persistence, fast local prototyping. Qdrant: Rust-native, payload indexing, sparse vectors. pgvector: PostgreSQL extension, IVFFLAT and HNSW indexes, operational simplicity tradeoff. Selection criteria matrix: scale, latency, cost, managed vs. self-hosted, hybrid search support, metadata filtering richness.

3. **hybrid-search-sparse-dense-retrieval.md**
   Why dense-only retrieval fails on head queries, exact terminology, and rare tokens. BM25 as sparse retrieval baseline: term frequency, inverse document frequency, length normalization (Robertson & Zaragoza formulation). Score fusion strategies: Reciprocal Rank Fusion (RRF — rank-based, parameter-free), linear combination (weighted dense + sparse scores), learned fusion (small model trained on relevance labels). When hybrid beats dense-only and when it doesn't. Implementation in Weaviate (bm25 + nearVector), Qdrant (sparse vectors), Elasticsearch (knn + query DSL). Cross-reference to RAG architecture file.

### Phase 3: Graph and Document Stores (3 files)

4. **property-graphs-neo4j-cypher.md**
   Property graph data model: nodes (with labels), relationships (with types), and properties on both. Neo4j architecture: native graph storage, index-free adjacency (O(1) relationship traversal), store layout (node store, relationship store, property store). Cypher query language: MATCH/WHERE/RETURN, CREATE/MERGE, aggregation, WITH chaining, OPTIONAL MATCH, variable-length path patterns. Use cases: recommendation engines, fraud detection, knowledge graphs, dependency analysis. Performance: when graph traversal beats SQL joins (multi-hop queries, relationship-heavy data). APOC procedures and GDS library (community detection, centrality, pathfinding).

5. **document-stores-mongodb-patterns.md**
   MongoDB document model: BSON, flexible schema, embedded documents vs. references. Aggregation pipeline: $match, $group, $lookup, $unwind, $project, $facet. Indexing: single-field, compound, text (full-text search), geospatial (2dsphere), partial, TTL. Data modeling patterns: one-to-many embedding (denormalized for read performance), one-to-many referencing (normalized for write consistency), subset pattern, bucket pattern for time-series, materialized-path pattern for tree structures. Transactions (multi-document ACID since 4.0; read/write concerns). When to choose MongoDB vs. PostgreSQL JSONB: schema flexibility vs. relational integrity guarantees.

6. **rdf-sparql-knowledge-graphs.md**
   RDF data model: subject-predicate-object triples, IRIs, blank nodes, typed literals, named graphs. SPARQL query forms: SELECT, CONSTRUCT, ASK, DESCRIBE; OPTIONAL, FILTER, UNION, property paths, aggregation. Ontology languages: RDFS (class/subclass, property hierarchy), OWL (cardinality constraints, equivalence, disjointness, reasoning). Triple stores: Apache Jena (TDB2), Virtuoso, Amazon Neptune (also property graph), Blazegraph. The knowledge-graph vs. property-graph tradeoff: RDF is standards-based and inference-capable but verbose; property graphs are developer-friendly and performance-optimized but lack formal semantics. Wikidata as a worked example of RDF at scale.

### Phase 4: Synthesis (3 files, requires approval)

7. **polyglot-persistence-selection-framework.md**
   The polyglot persistence principle: different data access patterns demand different storage engines; no single database is optimal for all workloads. Decision framework organized by access pattern: key-value lookup → Redis/DynamoDB; full-text search → Elasticsearch; relational queries with joins → PostgreSQL; graph traversal → Neo4j; semantic similarity → vector store; document flexibility → MongoDB; append-only event log → Kafka/Redis Streams. The operational cost of polyglot: connection management, consistency boundaries, cognitive load. When a single PostgreSQL instance (with JSONB, pgvector, full-text search) beats maintaining multiple specialized stores.

8. **sql-fundamentals-beyond-orm.md**
   Core SQL concepts the ORM abstracts away: query execution plans (EXPLAIN ANALYZE), index types (B-tree, hash, GIN, GiST), join algorithms (nested loop, hash join, merge join), transaction isolation levels (READ COMMITTED, REPEATABLE READ, SERIALIZABLE), MVCC (multi-version concurrency control), connection pooling semantics, prepared statements and query plan caching. Why understanding SQL matters even with an ORM: N+1 queries, index-missing performance cliffs, transaction boundary mistakes, lock contention. Cross-reference to Django ORM files.

9. **databases-synthesis-agent-implications.md**
   Capstone synthesis: how the databases/ domain grounds the AI retrieval-memory files and connects to systems-architecture. Key themes: (a) the ANN-algorithm file provides the theory that explains why vector-store retrieval has the performance characteristics the RAG files describe; (b) hybrid search explains why sparse+dense fusion is becoming the production default; (c) graph databases provide the explicit-relationship layer that vector similarity alone cannot; (d) polyglot persistence is the pragmatic framework for choosing among these options. Updated SUMMARY.md for the databases/ subdomain.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| ann-index-algorithms-hnsw-ivf-lsh | → ai/frontier/retrieval-memory/rag-architecture.md (dense retrieval), systems-architecture/content-addressable-storage-and-integrity.md (hash-based addressing) |
| vector-database-landscape-pinecone-weaviate-chroma | → ai/frontier/retrieval-memory/agentic-rag-patterns.md (product references), ai/frontier/retrieval-memory/persistent-memory-architectures.md (vector store critique) |
| hybrid-search-sparse-dense-retrieval | → ai/frontier/retrieval-memory/rag-architecture.md (BM25, reranking pipeline), ai/frontier/retrieval-memory/reranking-two-stage-retrieval.md |
| property-graphs-neo4j-cypher | → ai/frontier/retrieval-memory/persistent-memory-architectures.md (knowledge graph memory) |
| document-stores-mongodb-patterns | → django/django-orm-postgres.md (MongoDB vs PostgreSQL JSONB comparison) |
| rdf-sparql-knowledge-graphs | → ai/frontier/retrieval-memory/persistent-memory-architectures.md (knowledge graph section) |
| polyglot-persistence-selection-framework | → devops/redis-internals-and-operations.md, django/django-orm-postgres.md |
| sql-fundamentals-beyond-orm | → django/django-orm-postgres.md, django/django-database-pooling.md |
| databases-synthesis-agent-implications | → ai/frontier/retrieval-memory/rag-architecture.md, ai/frontier/retrieval-memory/persistent-memory-architectures.md |

## Duplicate coverage check

No existing file in the KB substantively covers any of the nine target topics. The closest overlaps are:
- redis-internals covers Redis ops but not data-modeling patterns → complementary, not duplicative
- persistent-memory-architectures discusses vector-store weaknesses conceptually but doesn't explain how they work → no duplication
- rag-architecture describes retrieval pipelines but treats the index as a black box → no duplication

## Formatting conventions

Based on review of existing SE files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `type`, `related`
- Markdown body: H1 title, H2 sections, H3 subsections, tables for structured comparisons, code blocks for examples
- Depth: 800–1500 words per file; dense but readable; cite specific systems, algorithms, and benchmarks
