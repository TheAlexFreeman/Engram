---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: property-graphs-neo4j-cypher.md, rdf-sparql-knowledge-graphs.md, vector-database-landscape-pinecone-weaviate-chroma.md
---

# Document Stores: MongoDB Data Modeling Patterns

**Document stores** are NoSQL databases that persist data as self-describing documents (JSON/BSON, XML) rather than normalised rows in typed tables. MongoDB is the dominant document store and has largely defined the ecosystem's patterns, tooling, and vocabulary. The document model excels at hierarchical data that is naturally read or written as a unit — user profiles, product catalogs, content management, event logs — where the relational model imposes artificial normalisation that increases join complexity without corresponding benefit.

---

## The Document Model

### Core Structure

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "username": "afreeman",
  "email": "alex@example.com",
  "profile": {
    "fullName": "Alex Freeman",
    "age": 34,
    "preferences": ["reading", "hiking"]
  },
  "posts": [
    {"title": "First Post", "created": ISODate("2024-01-15"), "tags": ["intro"]},
    {"title": "Second Post", "created": ISODate("2024-02-01"), "tags": ["tech", "ai"]}
  ],
  "createdAt": ISODate("2024-01-01")
}
```

**Key characteristics:**
- **BSON (Binary JSON):** MongoDB's internal format; supports additional types (ObjectId, Date, Binary, Decimal128) beyond JSON
- **`_id` field:** Required; automatically created as ObjectId (12 bytes: 4-byte timestamp + 5-byte random + 3-byte counter); globally unique by design
- **Nested documents:** First-class — the `profile` subdocument is stored inline, not across a foreign key
- **Arrays:** First-class — `preferences` and `posts` are stored as embedded arrays; array elements are queryable and indexable
- **Flexible schema:** Different documents in the same collection can have different fields (though schema validation is available)

---

## Aggregation Pipeline

The aggregation pipeline replaced MongoDB's MapReduce as the standard analytics mechanism. Composed of stages that transform the document stream:

### Core Stages

| Stage | Purpose |
|-------|---------|
| `$match` | Filter (like WHERE) — use early to reduce data volume |
| `$project` | Shape output — include/exclude fields, compute new fields |
| `$group` | Group documents by an expression and compute aggregates |
| `$sort` | Sort by one or more fields |
| `$limit` / `$skip` | Pagination |
| `$lookup` | Left outer join to another collection |
| `$unwind` | Deconstruct an array field into one document per element |
| `$addFields` | Add computed fields to documents |
| `$facet` | Run multiple sub-pipelines in parallel; return combined result |
| `$bucket` | Categorise into ranges (histogram) |
| `$graphLookup` | Recursive graph traversal within a collection |

### Example: Tag Analytics

```javascript
db.posts.aggregate([
  { $match: { status: "published" } },           // filter first
  { $unwind: "$tags" },                           // one doc per tag
  { $group: {
      _id: "$tags",
      count: { $sum: 1 },
      avgViews: { $avg: "$views" }
  }},
  { $sort: { count: -1 } },
  { $limit: 20 }
])
```

### `$lookup` (Join)

```javascript
db.orders.aggregate([
  { $lookup: {
      from: "products",
      localField: "productId",
      foreignField: "_id",
      as: "productDetails"
  }},
  { $unwind: "$productDetails" },
  { $project: { orderId: 1, "productDetails.name": 1, quantity: 1 } }
])
```

`$lookup` performs a left outer join — documents without a matching product retain all fields, with `productDetails` as an empty array. Performance: requires an index on `products._id` (or the `foreignField`); works best within the same replica set / sharded cluster.

---

## Indexing

### Index Types

| Index Type | Use Case |
|-----------|---------|
| **Single-field** | Exact match and range queries on one field |
| **Compound** | Multiple fields; ESR rule (Equality → Sort → Range) |
| **Multikey** | Arrays — MongoDB creates one index entry per array element |
| **Text** | Full-text search: $text queries; optional language stemming |
| **Geospatial 2dsphere** | GeoJSON: `$near`, `$geoWithin`, `$geoIntersects` |
| **Geospatial 2d** | Legacy 2D plane for legacy coordinate pairs |
| **TTL (Time-To-Live)** | Automatically delete documents after a time field expires |
| **Partial** | Index only documents matching a filter expression |
| **Sparse** | Index only documents where the field exists |
| **Wildcard** | Index all or selected nested fields dynamically |

### ESR Rule for Compound Indexes

The ESR (Equality–Sort–Range) rule governs field ordering in compound indexes for optimal query support:

1. **Equality** fields first — fields used with exact match (`field: value`)
2. **Sort** fields second — fields in the query's `sort` clause
3. **Range** fields last — fields with `$gt`, `$lt`, `$in` on multiple values

```javascript
// Query: find active users in a region, sorted by joinDate
// Optimal index: { status: 1, region: 1, joinDate: 1, age: 1 }
//                 equality      sort         equality    range
db.users.createIndex({ status: 1, region: 1, joinDate: 1, age: 1 })
```

---

## Data Modeling Patterns

### Embedding vs Referencing

The central design decision: store related data *inside* the document (embedding) or in a separate document with a reference (referencing)?

| Criterion | Embedding | Referencing |
|-----------|-----------|-------------|
| **Read pattern** | Data always read together | Data often read independently |
| **Write pattern** | Updated as a unit | Updated independently |
| **Cardinality** | 1:1, 1:few | 1:many, many:many |
| **Document size** | Small to moderate (<16MB BSON limit) | Unbounded |
| **Consistency** | Always consistent (atomic document writes) | Requires application-level joins or $lookup |

**Rule of thumb:** If the child data is always accessed with the parent and the relationship is bounded, embed. If the child data is queried independently, referenced by multiple parents, or unbounded (user → infinite posts), reference.

### Materialized Path for Trees

For hierarchical data (categories, file systems, comment threads), the **materialized path** pattern stores the full path from root to node as a string:

```json
[
  { "_id": 1, "path": ",", "name": "root" },
  { "_id": 2, "path": ",1,", "name": "electronics" },
  { "_id": 3, "path": ",1,2,", "name": "phones" },
  { "_id": 4, "path": ",1,2,3,", "name": "smartphones" }
]
```

- **Find all descendants of node 2:** `{ path: /^,1,2,/ }` — prefix match
- **Find ancestors:** split path string
- **Depth:** count separators in path
- **Create index:** `{ path: 1 }` supports prefix queries efficiently

Trade-offs: fast reads, especially for subtree queries; writes require updating all descendant paths on move.

### Bucket Pattern for Time-Series

Instead of one document per event (high document count), **bucket** multiple events per document:

```json
{
  "_id": ObjectId("..."),
  "sensorId": "sensor-001",
  "bucketStart": ISODate("2024-01-01T00:00:00Z"),
  "bucketEnd": ISODate("2024-01-01T01:00:00Z"),
  "count": 3600,
  "measurements": [
    { "ts": ISODate("2024-01-01T00:00:01Z"), "value": 22.5 },
    { "ts": ISODate("2024-01-01T00:00:02Z"), "value": 22.6 },
    // ... up to 3600 per hour
  ],
  "summary": { "min": 22.1, "max": 23.4, "avg": 22.7 }
}
```

**Benefits:**
- Dramatically reduces document count (360 vs 1,296,000 per sensor per year)
- Pre-computed summaries avoid aggregation at query time
- Compatible with MongoDB's official time series collections (5.0+) which implement bucketing internally

---

## ACID Transactions

MongoDB has supported **multi-document ACID transactions** since version 4.0 (2018):

```javascript
const session = client.startSession();
session.startTransaction();
try {
  await orders.insertOne({ ... }, { session });
  await inventory.updateOne({ sku: "abc" }, { $inc: { qty: -1 } }, { session });
  await session.commitTransaction();
} catch (err) {
  await session.abortTransaction();
  throw err;
}
session.endSession();
```

**Performance notes:**
- Multi-document transactions have overhead (~2–3× single-document writes)
- Should be used when cross-document consistency is genuinely required
- Most document model patterns avoid the need for transactions by embedding related data together (single-document atomicity is always guaranteed without transactions)

---

## MongoDB vs PostgreSQL JSONB

Many workloads are well-served by PostgreSQL's **JSONB** column type, which stores JSON in a binary format with full indexing support. Choosing between them:

| Dimension | MongoDB | PostgreSQL JSONB |
|-----------|---------|-----------------|
| **Query language** | MQL / Aggregation Pipeline | SQL + JSONB operators (`@>`, `#>>`, `?`, etc.) |
| **Relational joins** | `$lookup` (limited to same cluster) | Native SQL JOINs with full planner support |
| **Full-text** | Text indexes + `$text` | tsvector/tsquery, pg_trgm |
| **Indexing on JSONB** | Automatic multikey indexes | GIN index required; explicit path indexing |
| **Transactions** | Multi-doc since 4.0 | Always; full xact semantics |
| **Schema flexibility** | Native | JSONB column beside typed columns |
| **Sharding** | Native | Foreign data wrappers; Citus extension |
| **Horizontal scale** | Strong native support | Requires Citus or application-level sharding |

**Choose MongoDB when:** Schema flexibility is critical at the collection level; horizontal write sharding is required; the team thinks in documents, not tables; avoiding joins is architecturally important.

**Choose PostgreSQL JSONB when:** Some entities are relational (typed tables with joins) and some are document-like; you want SQL expressiveness over all data; transactions across relational and document data are needed in the same query.

---

## References

1. Bradshaw, S. et al. (2019). *MongoDB: The Definitive Guide*, 3rd ed. O'Reilly
2. MongoDB Inc. (2024). "MongoDB Manual." mongodb.com/docs/manual
3. Copeland, R. (2013). *MongoDB Applied Design Patterns.* O'Reilly
4. MongoDB Inc. (2020). "MongoDB Schema Design Best Practices." developer.mongodb.com
5. Kleppmann, M. (2017). *Designing Data-Intensive Applications*, Ch. 2 (Data Models). O'Reilly
6. Stonebraker, M. (2010). "SQL Databases v. NoSQL Databases." *ACM Queue*, 8(4)
