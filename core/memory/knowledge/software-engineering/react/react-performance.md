---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - react-19-overview.md
  - tanstack-query.md
  - vite-react-build.md
  - ../web-fundamentals/browser-dom-events.md
---

# React Performance

Performance work in React follows a clear hierarchy: first eliminate unnecessary work (wrong renders), then minimize render cost (memoization), then virtualize large lists, then optimize the bundle. This file covers each layer with the React 19 context.

---

## 1. React.memo — when it helps and when it doesn't

`React.memo` wraps a component and skips re-rendering if props haven't changed (shallow comparison). But "props haven't changed" requires referential stability, which is often harder to guarantee than it seems.

### When memo actually helps

```typescript
// Component is expensive to render
const DataGrid = React.memo(function DataGrid({ rows, columns }: DataGridProps) {
  // Renders 500 row × 20 column grid — slow
  return ...;
});

// Parent re-renders frequently (e.g., on scroll) but DataGrid's props are stable
function Dashboard() {
  const [scrollY, setScrollY] = useState(0);  // changes on every scroll
  const rows = useStableRows();  // stable reference
  const columns = useMemo(() => COLUMNS, []);  // stable reference
  
  return <DataGrid rows={rows} columns={columns} />;  // memo saves the re-render
}
```

### When memo doesn't help (or hurts)

```typescript
// ❌ Memo is useless here — inline object is a new reference every render
const Parent = () => (
  <Memo'd Child style={{ color: "red" }} />  // new object every render → memo bypassed
);

// ❌ Memo costs more than it saves for trivial components
const Label = React.memo(({ text }: { text: string }) => <span>{text}</span>);
// The shallow prop comparison costs CPU cycles — renders are nearly free for this component

// ❌ Children prop always breaks memo — ReactNode is a new reference
const Memo'd = React.memo(({ children }: { children: React.ReactNode }) => ...);
// children is always a new object — memo never skips
```

**The right mental model**: memo is useful when (1) the component is genuinely expensive and (2) you can guarantee stable prop references.

---

## 2. useMemo and useCallback

### Primary use: referential stability (not "expensive computation")

```typescript
// ❌ Common misconception: useMemo is for "expensive" calculations
const sortedList = useMemo(() => list.sort(), [list]);
// sort() on a 50-item array is microseconds — not the right reason for useMemo

// ✅ Real reason: the sorted list is passed as a prop to a memo'd component
const sortedList = useMemo(() => [...list].sort(compareFn), [list]);
// If sortedList were a new array on every render, Memo'd Child would always re-render

// ✅ Dependency array stability
const config = useMemo(() => ({ timeout: 5000, retries: 3 }), []);
// Without useMemo: new object every render — any useEffect with config in its deps would re-fire
```

### useCallback: stable function references

```typescript
// ❌ New function every render → child re-renders even if memo'd
<Child onChange={(val) => setValue(val)} />

// ✅ Stable reference via useCallback
const handleChange = useCallback((val: string) => {
  setValue(val);
}, []);  // no deps — setValue from useState is stable

// Note: useCallback(fn, deps) is syntactic sugar for useMemo(() => fn, deps)
```

### The over-memoization trap

Every `useMemo`/`useCallback` has a cost: the closure allocation, the dependency array comparison, and the cognitive load of reasoning about the dependency list. Over-memoization is a real problem in codebases that apply it indiscriminately.

**Don't memoize**:
- Values that change every render anyway (their deps change)
- Cheap computations that don't impact reference stability
- Things not used in dependency arrays or passed to memo'd components

---

## 3. React 19 Compiler (React Forget)

React 19 ships a compiler (`react-compiler`) that automatically inserts memoization. It performs static analysis on your component code and:
- Adds `memo` to components automatically where beneficial
- Inserts `useMemo` and `useCallback` at call sites
- Ensures memoization is semantically correct (never skips a render that should happen)

### What this means for manual memoization

- **useMemo/useCallback for referential stability** — still write these for cases where explicit stable references are required (dependency arrays, passing to native event listeners, etc.)
- **React.memo** — the compiler handles most cases; manual memo for library-authored components the compiler can't see
- **Performance profiling changes** — the compiler's memoization may look different in DevTools

### Enabling the compiler (Vite)

```bash
npm install babel-plugin-react-compiler
```

```typescript
// vite.config.ts
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: ["babel-plugin-react-compiler"],
      },
    }),
  ],
});
```

As of React 19.0, the compiler is opt-in. Check current compiler docs for any `reactCompilerConfig` options.

---

## 4. useEffectEvent (React 19.2)

The stale closure problem: when an effect reads state but that state isn't in the dependency array, it reads stale values. The traditional fix (adding to deps) causes the effect to re-fire every time the state changes, which can create infinite loops.

```typescript
// ❌ Classic stale closure
useEffect(() => {
  const id = setInterval(() => {
    console.log(count);  // reads stale count — always 0
  }, 1000);
  return () => clearInterval(id);
}, []);  // count not in deps

// ❌ "Fix" that breaks behavior
useEffect(() => {
  const id = setInterval(() => {
    console.log(count);
  }, 1000);
  return () => clearInterval(id);
}, [count]);  // interval re-creates on every count change — not the same interval
```

`useEffectEvent` (also known as `useEvent` in drafts) marks a function as an "event" that always reads current values but doesn't participate in the reactivity model:

```typescript
import { experimental_useEffectEvent as useEffectEvent } from "react";

function Counter() {
  const [count, setCount] = useState(0);
  
  // logCount reads the current count but isn't a reactive value itself
  const logCount = useEffectEvent(() => {
    console.log(count);  // always the current count, never stale
  });
  
  useEffect(() => {
    const id = setInterval(() => {
      logCount();  // not in deps → effect doesn't re-fire when count changes
    }, 1000);
    return () => clearInterval(id);
  }, [logCount]);  // logCount is stable — effect fires once
}
```

Note: `useEffectEvent` is in React 19.2. It's experimental in earlier releases. Check the current React docs for stability status.

---

## 5. Virtualizing large lists

When rendering hundreds or thousands of rows, only render what's visible using TanStack Virtual.

### Basic row virtualization

```typescript
import { useVirtualizer } from "@tanstack/react-virtual";

function VirtualList({ items }: { items: User[] }) {
  const parentRef = React.useRef<HTMLDivElement>(null);
  
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,  // estimated row height in px
    overscan: 5,             // render 5 extra rows above/below visible area
  });
  
  return (
    <div ref={parentRef} style={{ height: "600px", overflow: "auto" }}>
      {/* Spacer div that takes up the total size of all items */}
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            ref={virtualizer.measureElement}  // needed for dynamic height measurement
            data-index={virtualItem.index}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <UserRow user={items[virtualItem.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Dynamic heights

When row heights vary (e.g., content wraps), use `measureElement` ref + an initial `estimateSize` function:

```typescript
const virtualizer = useVirtualizer({
  count: items.length,
  getScrollElement: () => parentRef.current,
  estimateSize: (index) => {
    // A smarter estimate based on content length
    return items[index].description.length > 100 ? 120 : 60;
  },
});
```

---

## 6. Code splitting

Split at route boundaries first — that's where users perceive loading the most.

### Route-level splitting (TanStack Router)

```typescript
// routes/analytics.tsx — the component file is loaded dynamically
export const Route = createFileRoute("/analytics")({
  component: lazyRouteComponent(() => import("../components/AnalyticsPage")),
});
// AnalyticsPage's JS is not included in the initial bundle
```

### Manual lazy split

```typescript
const HeavyChartComponent = React.lazy(() =>
  import("./HeavyChartComponent")
);

function Dashboard() {
  const [showChart, setShowChart] = useState(false);
  
  return (
    <div>
      <button onClick={() => setShowChart(true)}>Load Chart</button>
      {showChart && (
        <Suspense fallback={<ChartSkeleton />}>
          <HeavyChartComponent />
        </Suspense>
      )}
    </div>
  );
}
```

### When to split

- Route-level: always (TanStack Router does this naturally with `lazyRouteComponent`)
- Heavy modal content: on mount, before the user opens the modal
- Large third-party libs (map, rich-text editor, chart): split the entire feature
- Don't split small utilities or commonly used UI components — the extra network round-trip isn't worth it

---

## 7. Bundle analysis

### rollup-plugin-visualizer

```typescript
// vite.config.ts
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: "dist/bundle-report.html",
      open: true,          // open in browser after build
      gzipSize: true,
      brotliSize: true,
      template: "treemap", // or "sunburst" or "network"
    }),
  ],
  build: { ... },
});
```

### Reading the report

- **Big blocks** = large modules; identify if they can be:
  - Split (lazy import)
  - Replaced with a lighter alternative
  - Only imported for the functionality actually used (tree-shaking issue → check if named imports work)
  
- **Duplicate packages** = two versions of the same library bundled separately; common with mismatched peer dependencies; fix by hoisting dependency versions

- **`node_modules` percentage** = typically 80%+ is normal; check if vendor bundle can be split for better cache reuse

---

## 8. React DevTools Profiler

The Profiler tab records render timings during user interactions.

### Workflow

1. Open React DevTools → Profiler tab
2. Click "Record" (circle button)
3. Perform the interaction you want to profile
4. Click "Stop"
5. Analyze the flame graph

### Reading results

- **Flame graph**: rows = components; width = render duration; gray = not rendered this commit
- **Ranked chart**: lists components by total render time; fastest path to finding expensive components
- **Why did this render?**: for each component, shows what triggered the re-render (prop changed, state changed, parent re-rendered, hooks changed)
- **Commits**: each bar in the timeline = one React commit (state update); tall bars = slow renders

### React 19 Chrome DevTools integration

React 19 adds performance marks to the browser's Performance timeline. Open Chrome DevTools → Performance tab to see "Component Render" and "Effect" timings alongside CPU/network profiles.

---

## 9. useTransition and useDeferredValue

React's concurrency APIs allow non-urgent renders to be pre-empted by urgent ones (like user input).

### useTransition

```typescript
function SearchPage() {
  const [query, setQuery] = useState("");
  const [isPending, startTransition] = useTransition();
  
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);  // urgent: update input immediately
    
    startTransition(() => {
      // Non-urgent: let React defer this if needed
      setFilter(e.target.value);  // filter triggers expensive re-render
    });
  };
  
  return (
    <>
      <input value={query} onChange={handleSearch} />
      {isPending && <Spinner />}  {/* show while transition is pending */}
      <FilteredList filter={filter} />
    </>
  );
}
```

### useDeferredValue

```typescript
function FilteredList({ query }: { query: string }) {
  // `deferredQuery` lags behind `query` — React renders with the stale value
  // while computing the expensive new render in the background
  const deferredQuery = useDeferredValue(query);
  
  // isStale is true while the deferred value hasn't caught up
  const isStale = deferredQuery !== query;
  
  const filtered = useMemo(
    () => items.filter((item) => item.name.includes(deferredQuery)),
    [deferredQuery]
  );
  
  return (
    <ul style={{ opacity: isStale ? 0.5 : 1 }}>  {/* dimmed while updating */}
      {filtered.map((item) => <li key={item.id}>{item.name}</li>)}
    </ul>
  );
}
```

### When to use each

| API | Best for |
|---|---|
| `useTransition` | Wrapping a state setter — marks the downstream render as non-urgent |
| `useDeferredValue` | When you receive a value as a prop and can't own the state setter |
| Both | Keeping user input responsive while expensive filtering/rendering catches up |
