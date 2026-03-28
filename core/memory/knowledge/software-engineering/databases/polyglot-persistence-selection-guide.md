---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: vector-database-landscape-pinecone-weaviate-chroma.md, ann-index-algorithms-hnsw-ivf-lsh.md, hybrid-search-sparse-dense-retrieval.md, property-graphs-neo4j-cypher.md, document-stores-mongodb-patterns.md, rdf-sparql-knowledge-graphs.md, SUMMARY.md, ../../../ai/frontier/retrieval-memory/rag-architecture.md
---

# Polyglot Persistence: A Database Selection Guide

Polyglot persistence is the practice of using multiple database technologies — each suited to a specific data type, access pattern, or performance requirement — within a single system. Modern applications routinely combine three or more data stores. This guide provides a decision framework for selecting among the paradigms covered in the databases/ subdomain and for designing multi-database architectures.

---

## The Core Question

**Which database for which use case?** The naïve view is that one database fits all; the polyglot view is that different data types have different optimal representations, and forcing all data into one storage model leads to poor performance, complex code, or both.

The databases/ subdomain covers six paradigms:

| Paradigm | Primary Model | Subdomain File |
|----------|--------------|---------------|
| Relational (PostgreSQL) | Tables, normalization, JOINs, ACID | (prerequisite; not created in this project) |
| Vector store | Embedding vectors, ANN search | `ann-index-algorithms-hnsw-ivf-lsh.md`, `vector-database-landscape-pinecone-weaviate-chroma.md` |
| Hybrid search | Sparse + dense retrieval | `hybrid-search-sparse-dense-retrieval.md` |
| Property graph | Nodes, edges, properties | `property-graphs-neo4j-cypher.md` |
| Document store | JSON/BSON documents, flexible schema | `document-stores-mongodb-patterns.md` |
| RDF / Knowledge graph | Subject-predicate-object triples, ontologies | `rdf-sparql-knowledge-graphs.md` |

---

## Decision Framework

### Step 1: Primary Access Pattern

| Access Pattern | Best Paradigm |
|---------------|---------------|
| Structured queries with JOINs; strong ACID; tabular data | **Relational (PostgreSQL)** |
| Semantic similarity search over embeddings | **Vector store** (dedicated) or **pgvector** |
| Keyword + semantic hybrid retrieval | **Hybrid search pipeline** |
| Multi-hop relationship traversal; graph analytics | **Property graph (Neo4j)** |
| Flexible schema; nested documents; horizontal scale | **Document store (MongoDB)** |
| Ontology reasoning; SPARQL; linked data standards | **RDF triple store** |

### Step 2: Scale Requirements

| Scale | Recommendation |
|-------|----------------|
| < 1M rows / < 100K vectors | Single PostgreSQL instance (+ pgvector) |
| 100K–10M vectors, moderate query rate | Chroma (local) or pgvector with HNSW |
| 10M+ vectors or high QPS | Dedicated vector store (Pinecone, Weaviate, Qdrant) |
| Graph: < 10M nodes | Neo4j Community (single node) |
| Graph: 10M+ nodes or HA required | Neo4j Enterprise (Causal Cluster) or ArangoDB |
| Document: < 10M docs, vertical scale acceptable | MongoDB single replica set |
| Document: 10M+ docs or global distribution | MongoDB sharded cluster or Cosmos DB |

### Step 3: Consistency Requirements

| Requirement | Choose |
|------------|--------|
| Multi-record ACID transactions (financial, inventory) | PostgreSQL or MongoDB 4.0+ |
| Eventual consistency acceptable (search index, embeddings) | Distributed vector store, Elasticsearch |
| Lineage and provenance (audit trail required) | RDF quads / named graphs |
| Immutable append-only log | Time-series DB (InfluxDB) or PostgreSQL with partitioning |

---

## Paradigm-by-Paradigm Guidance

### PostgreSQL: The Default Choice

PostgreSQL should be the **default starting point** for most applications. Reasons:
- ACID transactions with full SQL expressivity
- JSONB for flexible schema when needed (partially replaces document store)
- **pgvector** extension for vector ANN search (HNSW or IVFFlat)
- Full-text search via `tsvector`/`tsquery` (partially replaces search engine)
- Row-level security, rich type system, mature tooling

**Use PostgreSQL alone when**: operational simplicity matters more than peak performance; the team has SQL expertise; and scale is moderate (< 100M rows, < 1M vectors with pgvector).

**Switch away when**: ANN search requires more than pgvector can deliver (> 1B vectors, sub-10ms at high QPS), or when graph traversal is the primary access pattern (pgvector does not support graph queries).

### Dedicated Vector Store

Dedicated vector stores (Pinecone, Weaviate, Qdrant, Chroma) provide:
- Purpose-built HNSW or SPANN indices optimized for billion-scale search
- Metadata filtering combined with ANN search
- Multitenancy and access control
- Managed embedding update pipelines

**Choose Pinecone or Weaviate when**: production-grade SLA required with minimal operational overhead; Pinecone is fully managed (no infrastructure management); Weaviate provides more flexibility including self-hosted options.

**Choose Chroma or Qdrant when**: self-hosted, cost-sensitive, or development/research workloads. Chroma is particularly simple to embed in Python applications.

### Graph Database (Neo4j)

Graph databases win when the primary access pattern involves:
- Variable-depth relationship traversal (e.g., find all paths between two nodes up to 5 hops)
- Pattern matching over graph structure (e.g., fraud ring detection)
- Real-time recommendation (user → purchases → similar users → their purchases)
- Dependency analysis (package graphs, infrastructure dependency maps)

**Do not use a graph DB when**: most queries are simple lookups by ID; there are no meaningful relationships between entities; the data is tabular.

### Document Store (MongoDB)

MongoDB wins when:
- Schema evolution is rapid (different documents in the same collection have different fields)
- The natural unit of access is a nested JSON document (e.g., user profile with nested preferences, history, settings)
- Horizontal scale via sharding is required before relational maturity is needed
- The team has JavaScript/JSON-native workflow

**Avoid MongoDB when**: you need strong relational integrity across documents (use PostgreSQL foreign keys + ACID instead); or you need SPARQL or graph queries.

### RDF Triple Store

Use RDF when:
- You are publishing to or consuming from the Semantic Web / Linked Open Data
- The data model requires formal ontology reasoning (OWL inference)
- Provenance and named graphs (tracking who asserted what fact and when) are essential
- You need to integrate vocabularies from multiple organizations (SKOS, Schema.org)

**RDF is the right choice for**: knowledge graphs that need to interoperate with external datasets (Wikidata, DBpedia, SNOMED CT); digital humanities and cultural heritage projects; regulatory reporting with formal ontologies.

**RDF is overkill for**: most application databases; performance-sensitive retrieval (SPARQL is slower than SQL for simple lookups); teams without semantic web expertise.

---

## Multi-Database Architectures

### Common Polyglot Combinations

**RAG / Agent Memory System** (the most relevant combination for Engram):

```
PostgreSQL (relational metadata + operational state)
    +
Dedicated vector store (embedding index for semantic retrieval)
    +
Property graph (knowledge graph relationships)
    +
Redis (sub-millisecond cache + ephemeral session state)
```

Data synchronisation: a **change data capture (CDC)** pipeline (e.g., Debezium) streams updates from PostgreSQL to the vector store and graph whenever documents are created or updated.

**E-commerce Platform**:
```
PostgreSQL (orders, inventory, users — ACID required)
    +
MongoDB (product catalog — flexible schema, high read volume)
    +
Elasticsearch (full-text + faceted product search)
    +
Redis (session cache, rate limiting, flash sale counters)
```

**Knowledge Management + Semantic Search**:
```
RDF store (ontology + linked data backbone)
    +
Vector store (embedding-based semantic retrieval)
    +
PostgreSQL (access control, audit log, user management)
```

### Data Synchronisation Patterns

| Pattern | Use When | Trade-off |
|---------|---------|-----------|
| Write-through (synchronous dual write) | Consistency critical; throughput not primary | Latency of slowest store; write failures complex |
| Write-behind with CDC | High write throughput; eventual consistency acceptable | Replication lag; non-trivial CDC infrastructure |
| Event sourcing | Full audit history needed; time travel queries required | Complex read models; event schema evolution |
| Read-through cache (Redis) | Read-heavy access patterns; low latency required | Cache invalidation complexity; stale reads |

### Failure Mode Analysis

| Failure | Impact | Mitigation |
|---------|--------|-----------|
| Primary DB down | Writes unavailable | Multi-AZ replication; automatic failover |
| Vector index stale | Semantic retrieval returns outdated results | CDC replication; index rebuild procedures |
| Graph out of sync | Relationship queries miss recent updates | Transactional outbox pattern |
| Cache stampede (Redis eviction under load) | All requests hit DB simultaneously | Redis sentinel; circuit breaker pattern |

---

## Specific Guidance for RAG and Agent Memory Use Cases

### Choosing Databases for a RAG System

| RAG Component | Recommended Storage | Alternative |
|--------------|---------------------|-------------|
| Chunk metadata (source, date, section) | PostgreSQL | MongoDB |
| Dense embeddings (semantic retrieval) | Weaviate or Qdrant | pgvector (moderate scale) |
| Sparse inverted index (BM25) | Elasticsearch or pgvector FTS | Weaviate BM25 built-in |
| Conversation history | PostgreSQL + Redis (cache) | MongoDB |
| Agent working memory (ephemeral) | Redis | In-process dict |
| Long-term agent knowledge (Engram) | Markdown files + Git + vector index | PostgreSQL + pgvector |

### Engram-Specific Architecture Notes

The current Engram design stores knowledge as markdown files in Git. This is optimal for:
- Human readability and editability
- Version control and provenance (Git blame)
- Portability (no database dependency)

As scale grows, add:
1. **Vector index layer**: Build HNSW embeddings over file content for semantic `memory_search` queries (currently implemented in `core/tools/agent_memory_mcp/`)
2. **Metadata index**: PostgreSQL or SQLite for fast filtering by `trust`, `created`, `related`, tags
3. **Graph layer**: If relationship traversal across the `related:` graph becomes slow, migrate relationship index to a property graph

---

## References

1. Fowler, M. (2011). Polyglot Persistence. *martinfowler.com*.
2. Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly.
3. Sadalage, P. & Fowler, M. (2012). *NoSQL Distilled*. Addison-Wesley.
4. Hunger, M. et al. (2013). *Graph Databases*. O'Reilly.
5. Banker, K. (2011). *MongoDB in Action*. Manning.
6. Allemang, D. & Hendler, J. (2011). *Semantic Web for the Working Ontologist*. Morgan Kaufmann.
