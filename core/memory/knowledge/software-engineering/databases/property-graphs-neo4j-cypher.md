---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: rdf-sparql-knowledge-graphs.md, ann-index-algorithms-hnsw-ivf-lsh.md, hybrid-search-sparse-dense-retrieval.md
---

# Property Graphs: Neo4j and Cypher

**Property graphs** are a data model in which entities (nodes) and relationships (edges) can each carry arbitrary key-value properties, and relationships are first-class objects with types and directions. Unlike the relational model (entities as rows, relationships as foreign keys) and the RDF model (everything as subject-predicate-object triples), property graphs prioritise **navigational queries** — traversing networks of connected entities — over set-algebra joins. Neo4j dominates this space and has defined much of the practical vocabulary and tooling.

---

## The Property Graph Model

### Core Primitives

| Primitive | Description | Example |
|-----------|-------------|---------|
| **Node** | Entity; may have zero or more labels; carries property map | `(p:Person {name: "Alice", age: 32})` |
| **Label** | Type tag(s) on a node; multiple labels supported | `:Person`, `:Employee` |
| **Relationship** | Directed edge between two nodes; has exactly one type; carries property map | `[:KNOWS {since: 2020}]` |
| **Property** | Key-value pair on a node or relationship; values are primitive types or arrays | `{name: "Alice"}`, `{weights: [0.1, 0.3]}` |

**Key distinction from relational:** Relationships in property graphs are **stored as direct pointers** (index-free adjacency) — traversing from node A to node B is O(1), not O(log N) like a foreign key lookup into an index.

**Key distinction from RDF:** Nodes have identity beyond their properties (internal id); properties are not themselves nodes; relationships cannot participate in other relationships (no reification without adding a new node). Property graphs sacrifice formal semantics for query performance and development ergonomics.

---

## Neo4j Architecture

### Native Graph Storage

Neo4j's native graph storage implements **index-free adjacency**:

- Every node stores a linked list of its relationships (pointer to first relationship in both directions)
- Every relationship stores: start-node pointer, end-node pointer, next-relationship pointer for both start and end nodes
- **Traversal cost:** Following one relationship = follow a pointer — constant time, independent of graph size
- **Join cost in relational DB:** O(log N) index lookup per traversal step — N grows with dataset size

$$\text{Graph traversal time} = O(k) \text{ (property graph)} \quad \text{vs} \quad O(k \cdot \log N) \text{ (relational, N = table rows)}$$

where $k$ = number of traversal steps. For deep multi-hop queries, the advantage compounds exponentially.

**Storage layout:**
- `neostore.nodestore.db` — fixed-size node records (15 bytes per node), enabling direct offset lookup by node ID
- `neostore.relationshipstore.db` — fixed-size relationship records
- `neostore.propertystore.db` — variable-size property chains; large properties in adjacent blocks

### Transaction Model

Neo4j is ACID-compliant:
- **Write-ahead log (WAL):** All transactions written to transaction log before committing to store
- **Page cache:** Configurable in-memory page cache (typically 50% of RAM) for hot data; LRU eviction
- **Cluster mode (Causal Clustering):** Leader-follower replication; followers handle read queries; leader handles writes; Raft-based consensus

---

## Cypher Query Language

**Cypher** is Neo4j's declarative query language, designed around **ASCII-art pattern matching**:

```cypher
-- Find all people Alice knows who are older than 30
MATCH (alice:Person {name: "Alice"})-[:KNOWS]->(friend:Person)
WHERE friend.age > 30
RETURN friend.name, friend.age
ORDER BY friend.age DESC
LIMIT 10
```

### Core Clauses

| Clause | Purpose |
|--------|---------|
| `MATCH` | Pattern to find — nodes and/or relationships |
| `WHERE` | Filter condition on matched patterns |
| `RETURN` | Project output; can include aggregation |
| `WITH` | Pipe results to next MATCH (equivalent to subquery boundary) |
| `CREATE` | Create new nodes or relationships |
| `MERGE` | Find-or-create (upsert) pattern |
| `SET` / `REMOVE` | Update properties or labels |
| `FOREACH` | Iterate over a list in an update context |
| `UNWIND` | Expand a list into rows |
| `CALL` | Invoke a stored procedure or APOC function |

### Path Patterns

```cypher
-- Variable-length path: 1 to 5 hops
MATCH (a:Person)-[:KNOWS*1..5]->(b:Person)

-- Shortest path
MATCH p = shortestPath((a:Person)-[*]-(b:Person))
WHERE a.name = "Alice" AND b.name = "Bob"
RETURN p

-- All shortest paths
MATCH p = allShortestPaths((a)-[*]-(b))
```

Variable-length patterns enable traversals of arbitrary depth — the core capability that makes graph databases valuable for network analysis, recommendation, and dependency resolution.

### Aggregation and Collecting

```cypher
-- Count friendships per person
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, count(friend) AS friend_count

-- Collect into list
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, collect(friend.name) AS friends
```

---

## APOC Library

**APOC** (Awesome Procedures on Cypher) is the standard procedure library for Neo4j, providing 500+ utility functions:

| Category | Examples |
|----------|---------|
| **Graph algorithms** | `apoc.algo.dijkstra`, `apoc.algo.aStar` |
| **Data loading** | `apoc.load.json`, `apoc.load.csv`, `apoc.import.graphml` |
| **Refactoring** | `apoc.refactor.mergeNodes`, `apoc.refactor.setRelationshipType` |
| **Utilities** | `apoc.text.distance` (edit distance), `apoc.coll.partition`, `apoc.date.parse` |
| **Virtual graphs** | `apoc.graph.fromData` — create virtual graph for in-memory operations |

---

## Graph Data Science (GDS) Library

Neo4j's **GDS library** implements graph algorithms at scale using projected in-memory graphs:

### Workflow

```cypher
-- 1. Project the graph into memory
CALL gds.graph.project('myGraph', 'Person', 'KNOWS')

-- 2. Run an algorithm
CALL gds.pageRank.stream('myGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score
ORDER BY score DESC LIMIT 10

-- 3. Drop projection
CALL gds.graph.drop('myGraph')
```

### Algorithm Categories

| Category | Algorithms |
|----------|-----------|
| **Centrality** | PageRank, Betweenness Centrality, Degree Centrality |
| **Community detection** | Louvain, Label Propagation, Weakly/Strongly Connected Components |
| **Pathfinding** | Dijkstra, A*, Yen's k-shortest paths |
| **Similarity** | Node similarity, K-Nearest Neighbors (graph KNN) |
| **Node embedding** | FastRP, Node2Vec, GraphSAGE |
| **Link prediction** | Common Neighbours, Adamic-Adar, Resource Allocation |

**PageRank use case:** Fraud detection — fraudulent entities often form tight ring structures; their PageRank (and related authority scores) differs from legitimate entities. Running PageRank on a transaction graph identifies anomalous connectivity patterns.

---

## Use Cases Where Property Graphs Excel

### Knowledge Graphs

Knowledge graphs in a property graph model:
- Entities as nodes (`:Person`, `:Organization`, `:Topic`)
- Typed relationships (`:WORKS_AT`, `:AUTHORED`, `:RELATED_TO`)
- Query: "What topics are most related to authors who work at MIT?"

```cypher
MATCH (author:Person)-[:WORKS_AT]->(org:Organization {name: "MIT"})
      -[:AUTHORED]->(paper:Paper)-[:COVERS]->(topic:Topic)
RETURN topic.name, count(*) AS coverage
ORDER BY coverage DESC
```

### Fraud Detection

- Transaction graph: accounts as nodes, transactions as relationships with `amount`, `timestamp`
- Detect rings: sequences of transactions that return money to origin account (circular patterns)
- First-degree separation: flag accounts with many connections to known-bad accounts

```cypher
MATCH (a:Account)-[:TRANSACTED_WITH*2..4]->(a)  -- cycle detection
WHERE a.flagged = false
RETURN a.id, count(*) AS ring_count
ORDER BY ring_count DESC
```

### Dependency Analysis

Software repositories modelled as graphs: packages as nodes; `:DEPENDS_ON` relationships. Identify transitive dependencies, circular dependencies, and upgrade ripple effects — queries that are prohibitively expensive in relational models.

---

## Property Graph vs RDF: Comparison

| Dimension | Property Graph (Neo4j) | RDF/SPARQL |
|-----------|----------------------|-----------|
| **Data model** | Nodes + labeled edges + properties | Subject-predicate-object triples |
| **Identity** | Internal node ID | IRI (globally dereferenceable URL) |
| **Schema** | None required; labels as soft typing | RDFS/OWL ontology layers |
| **Reasoning** | No native entailment | OWL reasoners (EquivalentClass, subPropertyOf) |
| **Query language** | Cypher | SPARQL |
| **Linked data** | Not native | Core design goal |
| **Query performance** | Excellent (native graph store) | Variable; triplestore-dependent |
| **Tooling** | Neo4j ecosystem (mature) | Apache Jena, Virtuoso, Stardog |

**Choose property graph when:** Performance on navigational multi-hop queries matters; schema is flexible and evolving; team is application developers (not semantic web engineers).

**Choose RDF when:** Global identifier alignment across federated datasets matters; formal ontological reasoning is required; integration with Wikidata/DBpedia/linked data ecosystem is a goal.

---

## References

1. Robinson, I. et al. (2015). *Graph Databases: New Opportunities for Connected Data*, 2nd ed. O'Reilly
2. Needham, M. & Hodler, A.E. (2019). *Graph Algorithms: Practical Examples in Apache Spark and Neo4j.* O'Reilly
3. Neo4j Inc. (2024). "Neo4j Developer Documentation." neo4j.com/docs
4. Angles, R. & Gutiérrez, C. (2008). "Survey of Graph Database Models." *ACM Computing Surveys*, 40(1)
5. Lal, S. et al. (2021). "A Comprehensive Study of Graph Data Science Algorithms for Neo4j." arXiv 2101.10075
6. Buerli, M. (2012). "The Current State of Graph Databases." Department of Computer Science, Cal Poly
