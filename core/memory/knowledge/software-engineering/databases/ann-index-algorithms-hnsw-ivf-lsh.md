---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: vector-database-landscape-pinecone-weaviate-chroma.md, hybrid-search-sparse-dense-retrieval.md
---

# Approximate Nearest Neighbour: HNSW, IVF, and LSH

Exact nearest neighbour (kNN) search in high-dimensional vector spaces is computationally intractable at scale. **Approximate Nearest Neighbour (ANN)** algorithms trade bounded accuracy loss for dramatic latency and memory improvements, enabling semantic search, recommendation, and retrieval-augmented generation over billion-scale embedding corpora.

---

## The Exact kNN Problem

Given a query vector $q \in \mathbb{R}^d$ and a corpus $\mathcal{D} = \{x_1, \ldots, x_n\}$, exact kNN finds:

$$k\text{NN}(q) = \underset{S \subseteq \mathcal{D},\, |S|=k}{\operatorname{argmin}} \sum_{x \in S} d(q, x)$$

where $d$ is a distance metric (commonly Euclidean $L_2$, cosine distance, or inner product).

**Complexity:** Brute-force exact kNN requires $O(nd)$ distance computations per query — prohibitive when $n \geq 10^6$ and $d \geq 384$.

**The curse of dimensionality:** In high dimensions, the ratio of maximum to minimum pairwise distances tends toward 1, making indexing structures based on space partitioning (KD-trees) degrade to linear scan for $d \gtrsim 20$.

**ANN formulation:** Find $k$ vectors from $\mathcal{D}$ that are *approximately* nearest, accepting a recall target rather than exact correctness:

$$\text{Recall@k} = \frac{|\hat{S} \cap S^*|}{|S^*|}$$

where $S^*$ is the exact ground-truth k-nearest and $\hat{S}$ is the ANN result. Typical production targets: Recall@10 ≥ 0.95.

---

## Hierarchical Navigable Small World (HNSW)

### Core Idea

**HNSW** (Malkov & Yashunin, 2018) constructs a **multi-layer proximity graph**. The top layers are sparse long-range graphs (for rapid coarse navigation); lower layers are dense short-range graphs (for precise local search). Query traversal starts at the top, greedily descends toward query region, then performs beam search in dense bottom layer.

Inspired by small-world network theory (Watts-Strogatz): navigable graphs have short average path lengths while maintaining local clustering — enabling efficient greedy search.

### Data Structure

```
Layer 2 (sparse): [a]----[f]
                          |
Layer 1 (medium): [a]-[c]-[f]-[h]
                      |   |
Layer 0 (dense):  [a]-[b]-[c]-[d]-[e]-[f]-[g]-[h]-[i]
```

- Each vector $x_i$ is assigned a **maximum layer** $l_i \sim \text{Geometric}(p)$ (exponentially decreasing probability of higher layers)
- At each layer $\ell \leq l_i$, $x_i$ maintains edges to its $M$ nearest discovered neighbours
- Entry point: the vector with the highest layer assignment

### Insertion Algorithm

To insert a new element $q$:
1. Sample layer level $l \sim \lfloor -\ln(\text{Uniform}(0,1)) \cdot m_L \rfloor$ where $m_L = 1/\ln(M)$
2. From top layer, greedily navigate to layer $l+1$ finding closest element (greedy descent)
3. From layer $l$ down to layer 0: perform **ef_construction**-width beam search; connect $q$ to $M$ (or $M_{\text{max0}}$ for layer 0) nearest elements; optionally prune existing nodes' edge lists to maintain $M$ cap

### Query Algorithm

To find ef-nearest neighbours of $q$:
1. Greedy descent from top layer (1 candidate) through intermediate layers
2. At layer 0: beam search with **ef_search**-wide candidate list; return top-$k$

### Key Parameters

| Parameter | Role | Typical Range | Trade-off |
|-----------|------|--------------|-----------|
| `M` | Edges per node | 8–48 | ↑M: ↑recall, ↑memory, ↑build time |
| `ef_construction` | Build-time beam width | 100–500 | ↑ef_c: ↑recall, ↑build time |
| `ef_search` | Query-time beam width | 50–500 | ↑ef_s: ↑recall, ↑latency |
| `M_max0` | Layer-0 edges (default 2M) | 2×M | Higher connectivity at base layer |

### Complexity

| Operation | Complexity |
|-----------|-----------|
| Index build | $O(n \log n)$ expected |
| Query | $O(\log n)$ graph hops + $O(ef \cdot d)$ distance computations |
| Memory | $O(nMd)$ effective (graph + vectors) |

### Properties

- **State-of-the-art recall-latency trade-off** — routinely wins ANN benchmarks
- **No training phase** — online insertions supported
- **Deletion is hard** — requires soft-delete + periodic rebuild or complex re-linking; most implementations use lazy deletion
- **Memory-heavy** — graph structure adds significant overhead beyond raw vectors
- Implementations: **hnswlib** (reference C++), **faiss** (Meta), **Weaviate** (native HNSW), **pgvector** (HNSW backend added v0.5)

---

## Inverted File (IVF)

### Core Idea

**IVF** clusters the dataset using k-means and builds an **inverted index**: a map from cluster centroid to list of member vectors. At query time, the query is compared to centroids and only the `nprobe` closest clusters are searched exhaustively.

### Index Build

1. Train k-means clustering: $k$ centroids $\{c_1, \ldots, c_k\}$ on a sample of the corpus $\mathcal{D}$
2. Assign each vector $x_i$ to nearest centroid $c_j$
3. Store inverted lists: $L_j = \{x_i : c_j = \text{argmin}_c d(x_i, c)\}$

$$\text{IVF build cost} = O(k \cdot d \cdot n_{\text{train}} \cdot \text{iterations})$$

### Query

For query $q$:
1. Find `nprobe` nearest centroids: $\{c_{j_1}, \ldots, c_{j_p}\}$
2. Exhaustively compare $q$ to all vectors in corresponding inverted lists $L_{j_1} \cup \cdots \cup L_{j_p}$
3. Return top-$k$

$$\text{Expected scan per query} = n \cdot \frac{\text{nprobe}}{k}$$

### Key Parameters

| Parameter | Role | Typical Range |
|-----------|------|--------------|
| `nlist` (k) | Number of k-means clusters | $\sqrt{n}$ rule: $k \approx \sqrt{n}$ |
| `nprobe` | Clusters searched at query time | 1–100+ |

Increasing `nprobe` monotonically increases recall at cost of latency. At `nprobe = nlist`, IVF degenerates to exhaustive brute-force.

### IVF with Product Quantization (IVF-PQ)

**Product Quantization (PQ)** compresses stored vectors to reduce memory footprint:
1. Partition the $d$-dimensional space into $m$ subspaces of dimension $d/m$
2. Train $256$ centroids per subspace (1 byte per subspace → total $m$ bytes per vector)
3. Store compressed codes in inverted lists; compute approximate distances via precomputed lookup tables

$$\text{Asymmetric Distance Computation (ADC):} \quad \hat{d}(q, x) = \sum_{j=1}^{m} d_j(q_j, c_j^{(x)})$$

**IVF-PQ** is the dominant index type in Meta's faiss: excellent memory efficiency, good recall, GPU-friendly distance computation.

### IVF-HNSW Hybrid

Modern systems (faiss, Milvus) use **HNSW on centroids** to find nearest centroids faster than brute-force centroid scan, then fall back to IVF exhaustive list search. This eliminates the centroid scan cost for large `nlist`.

---

## Locality-Sensitive Hashing (LSH)

### Core Idea

**LSH** constructs hash functions with the property that **similar vectors are more likely to hash to the same bucket**. Multiple independent hash tables are built; a query vector is hashed into each table and candidate sets from matching buckets are merged.

### Random Projection LSH (for Cosine Similarity)

For cosine similarity (angular distance), the classic LSH family uses **random hyperplane hashing**:

$$h_{\mathbf{r}}(x) = \text{sign}(\mathbf{r}^\top x), \quad \mathbf{r} \sim \mathcal{N}(0, I_d)$$

**Collision probability:**
$$P(h_{\mathbf{r}}(x) = h_{\mathbf{r}}(y)) = 1 - \frac{\theta(x,y)}{\pi}$$

where $\theta(x,y)$ is the angle between vectors — more similar vectors hash together with higher probability.

**Compound hash (band):** Use $k$ bits composed into a single band; two vectors collide in a band iff all $k$ bits match → collision probability is $(1 - \theta/\pi)^k$.

### AND-OR Construction

Using $L$ hash tables each with $k$-bit compound hash:
- **AND rule (within table):** vectors must match all $k$ bits → reduces false positive rate
- **OR rule (across tables):** vectors matched in any of $L$ tables → reduces false negative rate

This gives LSH a characteristic S-curve recall-vs-similarity relationship:

$$P(\text{found}) = 1 - \left(1 - (1 - \theta/\pi)^k\right)^L$$

### E²LSH (Euclidean Distance)

For $L_2$ distance, the **p-stable distribution** family uses:

$$h_{a,b}(x) = \left\lfloor \frac{a^\top x + b}{w} \right\rfloor, \quad a \sim \mathcal{N}(0, I_d),\; b \sim \text{Uniform}[0, w]$$

with $w$ a bucket width parameter controlling the distance range being indexed.

### Properties

| Property | Value |
|----------|-------|
| Query time | $O(L \cdot k + |C| \cdot d)$ where $|C|$ = avg candidate set size |
| Memory | $O(nLk)$ — indexing overhead proportional to hash tables |
| Training | None (parameters chosen analytically) |
| Online insertion | Supported (hash new vector into all tables) |
| Deletion | Simple (remove from all tables) |
| Recall curve | Steeply parameterisable; hard to achieve recall >0.95 without huge memory overhead |

**LSH vs HNSW in practice:** LSH has been largely superseded by HNSW for in-memory ANN in most benchmarks. LSH remains relevant when:
- Online insertions/deletions are frequent (no rebuild required)
- Extreme memory constraints preclude graph storage
- Theoretical guarantees (probabilistic recall bounds) are required

---

## ANN Benchmarks

**ann-benchmarks.com** (Aumuller et al.) provides standardised recall-vs-queries-per-second plots across algorithms and datasets:

| Dataset | Dimensions | Size | Metric |
|---------|-----------|------|--------|
| SIFT-1M | 128 | 1M | L2 |
| GIST-1M | 960 | 1M | L2 |
| GloVe-100 | 100 | 1.2M | Cosine |
| Deep-1B | 96 | 1B | L2 |
| Text2Image-1B | 200 | 1B | IP |

**Benchmark findings (circa 2024-2025):**
- HNSW consistently dominates recall-QPS trade-off for in-memory indices
- IVF-PQ outperforms HNSW on GPU-accelerated and memory-constrained settings
- LSH algorithms generally underperform both in high-recall regime
- **DiskANN** (Microsoft, 2019) extends HNSW to disk-based indices for billion-scale datasets

---

## Metric Considerations

### Inner Product vs L2 vs Cosine

Most embedding models produce vectors where **cosine similarity** is the natural distance. Normalised vectors make $L_2$ and cosine equivalent:

$$\|x - y\|^2 = 2(1 - x^\top y) \quad \text{when } \|x\| = \|y\| = 1$$

**Maximum Inner Product Search (MIPS)** differs from cosine when vectors are not normalised. Matrix factorisation-based recommendation systems often require MIPS. Workarounds include Shrivastava-Li augmentation to convert MIPS to LSH-compatible problem.

### Choosing the Right Index

| Scenario | Recommended Index |
|----------|------------------|
| <1M vectors, high recall required | HNSW (hnswlib, pgvector) |
| >100M vectors, GPU available | IVF-PQ (faiss GPU) |
| Streaming inserts, moderate recall OK | LSH or HNSW with soft-delete |
| On-disk billion-scale | DiskANN / ScaNN |
| Hybrid sparse+dense | HNSW for dense + BM25 for sparse, merged via RRF |

---

## References

1. Malkov, Y.A. & Yashunin, D.A. (2020). "Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs." *IEEE TPAMI*, 42(4)
2. Johnson, J., Douze, M., & Jégou, H. (2021). "Billion-scale Similarity Search with GPUs." *IEEE TBIG*, 7(3) — faiss paper
3. Indyk, P. & Motwani, R. (1998). "Approximate Nearest Neighbors: Towards Removing the Curse of Dimensionality." *STOC'98*
4. Aumuller, M. et al. (2020). "ANN-Benchmarks: A Benchmarking Tool for Approximate Nearest Neighbor Algorithms." *Information Systems*, 87
5. Jayaram Subramanya, S. et al. (2019). "DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node." *NeurIPS 2019*
6. Charikar, M.S. (2002). "Similarity Estimation Techniques from Rounding Algorithms." *STOC'02* — hyperplane LSH
