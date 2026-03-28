---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: property-graphs-neo4j-cypher.md, ann-index-algorithms-hnsw-ivf-lsh.md, vector-database-landscape-pinecone-weaviate-chroma.md
---

# RDF, SPARQL, and Knowledge Graphs

**RDF** (Resource Description Framework) is the W3C-standardised data model for the Semantic Web, representing all facts as *triples* — (subject, predicate, object) — where subjects and predicates are identified by globally dereferenceable IRIs. **SPARQL** is the corresponding query language. Together they form the foundation for **knowledge graphs** that are interoperable across organisations and systems. Wikidata, Google's Knowledge Graph, and the linked open data cloud are the largest real-world deployments.

---

## The RDF Data Model

### Triples as the Atomic Unit

Every fact in RDF is expressed as a **triple** (subject, predicate, object):

```turtle
@prefix ex: <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

ex:Alice foaf:name "Alice Freeman" .
ex:Alice foaf:age 32 .
ex:Alice foaf:knows ex:Bob .
ex:Alice ex:worksAt ex:MIT .
ex:MIT rdfs:label "Massachusetts Institute of Technology" .
```

**Three types of RDF terms:**

| Type | Description | Example |
|------|-------------|---------|
| **IRI (Internationalized Resource Identifier)** | Global identifier, dereferenceable URL | `ex:Alice`, `foaf:name` |
| **Blank node** | Anonymous node, local scope only | `_:b1` |
| **Literal** | String, number, date, etc.; optionally typed or language-tagged | `"Alice Freeman"`, `32`, `"2024"^^xsd:gYear` |

**Key property:** IRIs are globally unique and dereferenceable — `ex:Alice` means the same thing everywhere and can be looked up to discover more facts. This enables **federated data integration** across different datasets that use the same IRIs.

### Named Graphs / Quads

SPARQL 1.1 extends triples to **quads** — triples with a *graph name* (the dataset they belong to):

```
<http://graph1> { ex:Alice foaf:name "Alice" }
<http://graph2> { ex:Alice foaf:name "Alice Freeman" }
```

Named graphs enable:
- Provenance tracking (which source asserted each fact)
- Temporal versioning (facts at different time points)
- Access control (different graphs visible to different users)
- Partitioning large knowledge graphs by domain

---

## SPARQL: Query Language

### Four Query Forms

| Form | Description |
|------|-------------|
| `SELECT` | Returns bindings for variables (table-like result) |
| `CONSTRUCT` | Returns an RDF graph constructed from matched patterns |
| `ASK` | Returns yes/no: does any match exist? |
| `DESCRIBE` | Returns the RDF description of a resource |

### SELECT Query Structure

```sparql
PREFIX ex: <http://example.org/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?name ?age
WHERE {
  ?person foaf:knows ex:Bob .
  ?person foaf:name ?name .
  OPTIONAL { ?person foaf:age ?age }
  FILTER(?age > 28)
}
ORDER BY DESC(?age)
LIMIT 10
```

**Pattern matching:** SPARQL's `WHERE` clause consists of triple patterns where variables (`?person`, `?name`) are bound to matching RDF terms.

### Property Paths

Property paths enable expressive path queries without specifying path length:

```sparql
-- transitive subClassOf (arbitrary depth rdfs:subClassOf chain)
?class rdfs:subClassOf* ex:BaseClass .

-- one or more hops of foaf:knows
?alice foaf:knows+ ?transitiveFriend .

-- alternative properties
?person (foaf:name|rdfs:label) ?label .

-- inverse
?org ^ex:worksAt ?employee .   -- equivalent to ?employee ex:worksAt ?org
```

### OPTIONAL and FILTER

```sparql
SELECT ?person ?email
WHERE {
  ?person foaf:name "Alice" .
  OPTIONAL { ?person foaf:mbox ?email }  -- left outer join
  FILTER(!BOUND(?email) || STRCONTAINS(STR(?email), "@mit.edu"))
}
```

### UNION

```sparql
SELECT ?person
WHERE {
  { ?person rdf:type ex:Student }
  UNION
  { ?person rdf:type ex:Professor }
}
```

### SPARQL Update

Standard SPARQL Update (SPARQL 1.1) supports modifying the graph:

```sparql
INSERT DATA {
  GRAPH <http://my-graph> {
    ex:Carol foaf:name "Carol" ;
             foaf:age  28 .
  }
}

DELETE { ?p foaf:age ?old }
INSERT { ?p foaf:age 29 }
WHERE  { ?p foaf:name "Carol" ; foaf:age ?old }
```

---

## Schema Layers: RDFS and OWL

RDF by itself carries no schema. Two schema languages add formal semantics:

### RDFS (RDF Schema)

Basic schema vocabulary:

| Term | Meaning |
|------|---------|
| `rdfs:Class` | Declares a resource to be an RDF class |
| `rdfs:subClassOf` | Subclass relationship (transitive) |
| `rdfs:subPropertyOf` | Subproperty relationship (transitive) |
| `rdfs:domain` | The class of subjects for a property |
| `rdfs:range` | The class of objects for a property |
| `rdfs:label` | Human-readable name |
| `rdfs:comment` | Human-readable description |

RDFS supports **limited inference**: if `ex:Alice rdf:type ex:Employee` and `ex:Employee rdfs:subClassOf ex:Person`, then a RDFS reasoner can infer `ex:Alice rdf:type ex:Person`.

### OWL (Web Ontology Language)

OWL adds significantly richer ontological constructs:

| OWL Construct | Description |
|---------------|-------------|
| `owl:equivalentClass` | Two classes have exactly the same extension |
| `owl:equivalentProperty` | Two properties are synonymous |
| `owl:sameAs` | Two IRIs denote the same real-world entity |
| `owl:inverseOf` | Property A is the inverse of property B |
| `owl:FunctionalProperty` | At most one value per subject |
| `owl:InverseFunctionalProperty` | Uniquely identifies subject from value |
| `owl:TransitiveProperty` | Transitivity: if A→B and B→C then A→C |
| `owl:SymmetricProperty` | If A→B then B→A |
| `owl:Restriction` | Property cardinality, value constraints |
| `owl:disjointWith` | Two classes share no members |

**OWL reasoning:** OWL reasoners (Pellet, HermiT, ELK) apply tableau algorithms to derive all logical entailments from OWL axioms. A reasoner can detect unsatisfiable classes (contradictions in the ontology) and compute the full class hierarchy.

**Complexity trade-offs:** Full OWL-DL is decidable but can be EXPTIME-complete; OWL-EL (subset used by SNOMED CT, Gene Ontology) is tractable in polynomial time.

---

## Triple Stores

| System | Deployment | Strengths |
|--------|-----------|-----------|
| **Apache Jena / TDB** | Open source, embedded or server | Full SPARQL 1.1; RDFS/OWL reasoning; widely used in research |
| **Virtuoso** | Open source + commercial | High performance; used by DBpedia/Wikidata public endpoint |
| **Amazon Neptune** | Managed cloud | Supports both RDF/SPARQL and Gremlin/property graph; serverless option |
| **Stardog** | Commercial | Strong OWL reasoning; virtual graphs (over RDBMS); SPARQL star |
| **GraphDB** | Commercial (free tier) | High-performance RDF; excellent SPARQL 1.1; used in enterprise KGs |
| **Blazegraph** | Open source | Powers Wikidata Query Service; SPARQL 1.1 with extensions |

---

## Wikidata: The Canonical Public Knowledge Graph

**Wikidata** (Wikimedia Foundation, 2012–present) is the largest publicly available structured knowledge graph, as of 2024:

- **~110 million items** (entities)
- **~1.5 billion statements** (triples / property-value pairs)
- **Multilingual:** Labels and descriptions in 300+ languages
- **Open license:** CC0 (public domain)
- **Query interface:** Wikidata Query Service at query.wikidata.org — SPARQL 1.1, publicly accessible

### Wikidata Schema

Wikidata uses a **statement model** rather than raw triples, to handle qualifiers and provenance:

```
(Alice, occupation, engineer)  [main triple]
  → qualifier: start time 2020
  → qualifier: employer: MIT
  → reference: source: LinkedIn
```

This is implemented with blank nodes (or RDF reification) — each statement is an object with the main value plus qualifiers plus source references. SPARQL queries must navigate this nesting.

### Example Wikidata SPARQL Query

```sparql
-- Find all female Fields Medal recipients and their birth countries
SELECT ?person ?personLabel ?birthCountryLabel
WHERE {
  ?person wdt:P166 wd:Q103630 .    # award: Fields Medal
  ?person wdt:P21 wd:Q6581072 .    # sex: female
  ?person wdt:P19 ?birthPlace .    # place of birth
  ?birthPlace wdt:P17 ?birthCountry . # country
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
```

---

## Property Graph vs RDF: When to Use Each

| Scenario | Recommendation |
|----------|---------------|
| High-performance multi-hop traversal | Property graph (Neo4j) |
| Global IRI alignment with external datasets | RDF |
| Formal ontological reasoning (OWL) | RDF |
| Linked data / Wikidata integration | RDF |
| Developer teams (application-oriented) | Property graph |
| Semantic web researchers / enterprise knowledge graphs | RDF |
| Provenance and temporal versioning of facts | RDF (named graphs) |
| Graph analytics (PageRank, community detection) | Property graph (GDS) |

---

## References

1. W3C (2014). "RDF 1.1 Concepts and Abstract Syntax." w3.org/TR/rdf11-concepts
2. W3C (2013). "SPARQL 1.1 Query Language." w3.org/TR/sparql11-query
3. Hitzler, P. et al. (2009). *OWL 2 Web Ontology Language Primer.* W3C Recommendation
4. DuCharme, B. (2013). *Learning SPARQL*, 2nd ed. O'Reilly
5. Vrandečić, D. & Krötzsch, M. (2014). "Wikidata: A Free Collaborative Knowledgebase." *Communications of the ACM*, 57(10)
6. Angles, R. et al. (2017). "Foundations of Modern Query Languages for Graph Databases." *ACM Computing Surveys*, 50(5)
7. Pan, J.Z. et al. (2017). *Exploiting Linked Data and Knowledge Graphs in Large Organisations.* Springer
