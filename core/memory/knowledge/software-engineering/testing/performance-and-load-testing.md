---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - system-and-acceptance-testing.md
  - software-qa-metrics-process.md
---

# Performance and Load Testing

Performance testing verifies that a system meets its speed, throughput, and reliability requirements under specified conditions. It is non-functional testing: the question is not "does it work?" but "does it work well enough?"

---

## 1. Latency percentile discipline

**Mean latency is almost useless** for characterizing user-facing performance. It is dominated by the common case and hides the tail. Users completing slow requests don't experience the mean; they experience their specific percentile.

**The percentile hierarchy:**
| Percentile | Meaning |
|-----------|---------|
| p50 | Median latency — half of requests complete faster |
| p75 | 75% of requests complete at or below this latency |
| p95 | 95% of requests — the "most users" threshold |
| p99 | 1 in 100 requests — often the SLA commitment |
| p99.9 | 1 in 1,000 — "three nines" tail |
| p99.99 | 1 in 10,000 — "four nines" tail; relevant for financial systems |

**Why tail latency matters:**
1. **User experience:** A user completing 5 API calls per page load is likely to experience the p99 or worse of any single call
2. **Fan-out amplification:** In microservices, a page load may fan out to 10-50 downstream services. If each service has 1% p99 outliers, the probability that at least one is slow is $1 - 0.99^{50} \approx 39\%$.
3. **SLA commitments:** SLAs are typically stated in p95 or p99 terms, not mean terms

**Histogram and HDR histogram:** Store latency as a histogram, not as running mean. HdrHistogram provides accurate high-dynamic-range latency histograms at near-zero cost. Prometheus's histogram metric type stores latencies in configurable buckets.

---

## 2. Types of performance tests

### 2.1 Load testing

Verify the system meets its SLAs at **expected production traffic levels**.

**Setup:**
- Define anticipated traffic: requests per second, concurrent users, transaction mix
- Run for a representative duration (at least 5-10 minutes after warmup)
- Verify that p95/p99 latencies meet SLAs and error rates remain below threshold

**Questions answered:** Does the system hold up under normal expected load? Are there any gradual degradation patterns (memory accumulation, connection pool exhaustion)?

### 2.2 Stress testing

Push the system **beyond expected load** to find the breaking point.

**Setup:**
- Gradually increase load until the system degrades visibly (error rate rises, latency spikes)
- Identify where the system fails (which component becomes the bottleneck first)
- Observe recovery behavior when load is reduced (does the system recover automatically?)

**Questions answered:** What is the system's capacity? Where does it break? Does it fail gracefully or catastrophically? Does it recover without human intervention?

### 2.3 Soak testing (endurance testing)

Run at moderate load for **extended duration** (hours to days).

**Setup:**
- Run at 50-70% of peak load for 4-72 hours
- Monitor memory usage, file descriptor counts, connection pool size, disk space

**Questions answered:** Are there memory leaks? Connection pool exhaustion over time? Log files filling disk? Gradual performance degradation? Bugs that only appear after extended operation.

**What soak tests find:** Memory leaks are invisible in short tests. Connection leaks (connections that are opened but never closed) accumulate slowly. Temporary files that should be cleaned up but aren't. Thread pool saturation under sustained load.

### 2.4 Spike testing

Test response to **sudden, dramatic load increases** (e.g., celebrity mention, viral social media event, scheduled batch job).

**Setup:**
- Baseline load → sudden 10x-100x spike → back to baseline
- Measure: time to detect and handle the spike; error rate during the spike; latency during the spike; time to return to baseline performance after the spike

**Questions answered:** Does the system auto-scale appropriately? What is the impact on users during the spike? Does the system recover cleanly after the spike?

### 2.5 Volume testing

Verify system behavior when dealing with **large amounts of data** (large files, large database tables, large message payloads).

Distinct from load testing (which varies concurrent users); volume testing holds concurrent users constant but varies data size.

---

## 3. Performance testing tools

| Tool | Type | Language | Notes |
|------|------|----------|-------|
| **k6** | Load, stress, soak | JavaScript/Go | Modern; scriptable; good metrics export; free CLI |
| **Locust** | Load, stress | Python | Scriptable in Python; great for Python teams; distributed mode |
| **JMeter** | Load, stress | GUI/XML | Widely used; complex configuration; good enterprise support |
| **Gatling** | Load, stress | Scala/DSL | High-performance; excellent HTML reports |
| **wrk / wrk2** | HTTP benchmarking | C | Lightweight; for quick HTTP endpoint benchmarks |
| **Artillery** | Load | YAML/JS | Simple YAML configuration; cloud mode available |

**Example k6 load test:**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // ramp up to 50 users
    { duration: '5m', target: 50 },    // hold at 50 users
    { duration: '30s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // p95 < 500ms
    http_req_failed: ['rate<0.01'],    // < 1% error rate
  },
};

export default function () {
  const response = http.get('https://staging.example.com/api/products');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

---

## 4. Profiling as testing

When a load test reveals a performance SLA violation, profiling attributes the latency to specific components.

### 4.1 Types of profiling

**CPU profiling:** Identifies which functions consume the most CPU time. Use sampling profilers (low overhead, statistical) for production-like environments; use instrumentation profilers (higher overhead, exact call counts) for detailed analysis.

**Memory profiling:** Identifies which objects consume memory and where they are allocated. Essential for soak test investigations (memory leaks).

**I/O profiling:** Identifies slow disk reads/writes, database queries, and network calls. Often the primary source of latency in web applications.

### 4.2 Flame graphs

A flame graph visualizes the call stack sampled many times during execution:
- The x-axis represents time (or samples); width = fraction of total time
- The y-axis represents call depth; the bottom is the entry point
- The top of each "flame" is the function doing actual work; functions below it are callers

**Reading flame graphs:**
- Wide boxes at the top = hot code paths (where time is spent)
- Wide boxes in the middle = expensive callers that invoke many different callees
- Unexpected width in library functions = investigate those library calls (N+1 queries, un-cached lookups)

**Tools:**
- **py-spy** (Python): sampling profiler; works on running production processes; generates flame graphs directly
- **cProfile + snakeviz** (Python): instrumentation profiler; good for test-run analysis
- **perf + Brendan Gregg's FlameGraph** (Linux, C/C++): the canonical flame graph tool
- **async-profiler** (Java): modern, low-overhead profiling for JVM with flame graph output
- **0x** (Node.js): flame graph profiler built on V8 profiling

### 4.3 The observer effect in profiling

Profiling instruments the program, which changes its behavior. Sampling profilers introduce minimal overhead (1-5%); instrumentation profilers can add 2-10x overhead. Always benchmark with the profiler off to confirm the profiler hasn't introduced false performance characteristics. For production profiling of live systems, use sampling profilers only.

---

## 5. Chaos engineering

Chaos engineering (developed at Netflix, circa 2011) deliberately injects failures into a running system — in production or staging — to test that the system degrades gracefully and recovers automatically.

**Principle:** The system will experience failures in production. Better to discover failure modes in deliberate, controlled experiments than in uncontrolled incidents.

**The chaos engineering workflow:**
1. **Define steady state:** A measurable metric (request success rate, latency, revenue) that indicates normal operation
2. **Hypothesize:** "We believe the system will maintain steady state when X fails"
3. **Inject failure:** Kill instances, degrade network (add latency, packet loss), corrupt responses, exhaust resources (fill disk, consume CPU)
4. **Observe:** Does steady state hold? What degrades? What cascades?
5. **Fix:** If steady state breaks, identify and fix the brittleness
6. **Automate:** Make the experiment repeatable and add it to the continuous chaos schedule

**Tools:**
- **Chaos Monkey** (Netflix, open source): randomly kills production instances
- **Gremlin** (commercial): full chaos engineering platform; network impairments, CPU/memory consumption, state attacks
- **Chaos Toolkit** (open source Python): declarative chaos experiments
- **Litmus** (Kubernetes): chaos experiments as Kubernetes custom resources
- **Toxiproxy** (Shopify): network proxy for simulating network conditions in testing

**Game day:** A scheduled event where the team runs chaos experiments together and observes the system's response. Used to verify disaster recovery procedures, identify unknown single points of failure, and build team confidence in incident response.

---

## 6. Performance SLA design

**SLA vs. SLO vs. SLI:**
- **SLI** (Service Level Indicator): the metric measured (p99 latency, availability rate)
- **SLO** (Service Level Objective): the target value ("p99 latency < 500ms over 30-day window")
- **SLA** (Service Level Agreement): a contractual commitment, often with financial penalties for violation

**Setting realistic SLOs:**
1. Measure current performance in production (p50, p95, p99) as a baseline
2. Set SLO targets slightly tighter than the measured baseline to push gradual improvement
3. Account for deployment overhead, warm-up time, and routine spike behavior
4. Define the measurement window (instantaneous? rolling 5 minutes? rolling 30 days?)

**Error budget:** `error_budget = 1 - SLO_target`. If SLO is 99.9% availability, the error budget is 0.1% — about 43 minutes per month. Error budget thinking transforms "reliability vs. velocity" from a conflict into a shared resource to allocate: spend error budget on risky deployments; replenish error budget with reliability improvements.
