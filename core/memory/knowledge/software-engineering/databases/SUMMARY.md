---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: ann-index-algorithms-hnsw-ivf-lsh.md, vector-database-landscape-pinecone-weaviate-chroma.md, hybrid-search-sparse-dense-retrieval.md, property-graphs-neo4j-cypher.md, document-stores-mongodb-patterns.md, rdf-sparql-knowledge-graphs.md, polyglot-persistence-selection-guide.md
---

# Databases — Subdomain Summary

This subdomain (`software-engineering/databases/`) covers the major database paradigms relevant to modern AI and agent systems, including vector stores, hybrid search, graph databases, document stores, RDF/knowledge graphs, and a polyglot persistence decision guide.

**Prerequisites**: Familiarity with relational databases and SQL. The relational paradigm (PostgreSQL) is a prerequisite for most files but is covered in the broader software-engineering domain rather than here.

---

## Files in This Subdomain

| File | One-Line Description |
|------|----------------------|
| `ann-index-algorithms-hnsw-ivf-lsh.md` | HNSW, IVFFlat, and LSH algorithms for approximate nearest-neighbor search; complexity, trade-offs, and benchmarks |
| `vector-database-landscape-pinecone-weaviate-chroma.md` | Survey of dedicated vector databases: architecture, managed vs self-hosted, filtering, and use case fit |
| `hybrid-search-sparse-dense-retrieval.md` | Combining BM25 sparse retrieval with dense vector retrieval; reciprocal rank fusion; query expansion |
| `property-graphs-neo4j-cypher.md` | Property graph model, index-free adjacency, Cypher query language, GDS algorithms, and fraud detection patterns |
| `document-stores-mongodb-patterns.md` | MongoDB BSON/aggregation pipeline, compound index ESR rule, embedding vs referencing, bucket pattern, ACID since 4.0 |
| `rdf-sparql-knowledge-graphs.md` | RDF triples, SPARQL query forms, RDFS/OWL ontologies, triple store comparison, Wikidata worked example |
| `polyglot-persistence-selection-guide.md` | Decision framework: when to use which database; multi-database architectures; synchronisation patterns; RAG and Engram guidance |

---

## Recommended Reading Order

**If entering from AI systems / RAG angle**:
1. `ann-index-algorithms-hnsw-ivf-lsh.md` — how ANN search works
2. `vector-database-landscape-pinecone-weaviate-chroma.md` — which vector store to choose
3. `hybrid-search-sparse-dense-retrieval.md` — combining sparse and dense retrieval
4. `polyglot-persistence-selection-guide.md` — fit into broader data architecture

**If entering from knowledge graph / semantic web angle**:
1. `rdf-sparql-knowledge-graphs.md` — RDF/SPARQL fundamentals
2. `property-graphs-neo4j-cypher.md` — property graph alternative
3. `polyglot-persistence-selection-guide.md` — when to choose which

**If building a document-centric application**:
1. `document-stores-mongodb-patterns.md` — MongoDB patterns
2. `polyglot-persistence-selection-guide.md` — where document store fits in the stack

---

## Cross-References

**Upstream** (AI frontier):
- `../../../ai/frontier/retrieval-memory/rag-architecture.md` — application of vector store + hybrid search
- `../../../ai/frontier/retrieval-memory/agentic-rag-patterns.md` — multi-step retrieval using databases in this subdomain
- `../../../ai/frontier/multimodal/multimodal-rag-retrieval-patterns.md` — extends hybrid retrieval to multimodal content

**Lateral** (software engineering):
- `../systems-architecture/schema-evolution-strategies.md` — schema evolution concerns apply across all paradigms
- `../testing/` — database testing patterns and query validation
