---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - django-migrations-advanced.md
  - django-production-stack.md
  - django-security.md
  - psycopg3-and-connection-management.md
---

# Django ORM & PostgreSQL Features

Covers ORM patterns and PostgreSQL-specific capabilities relevant to a Django/Postgres stack. Includes changes through Django 6.0.

## QuerySet fundamentals (advanced patterns)

### select_related vs prefetch_related
```python
# select_related: JOINs (use for ForeignKey / OneToOne)
orders = Order.objects.select_related("user", "user__profile")

# prefetch_related: separate queries + Python join (use for M2M, reverse FK)
orders = Order.objects.prefetch_related(
    Prefetch("items", queryset=OrderItem.objects.select_related("product"))
)
```

`select_related` uses SQL joins in one query. `prefetch_related` issues additional queries and joins in Python specifically to avoid the classic N+1 pattern on reverse relations and M2M data.

### only() and defer()
```python
# Load only specific fields (generates SELECT with named columns):
users = User.objects.only("id", "email")

# Defer expensive fields:
users = User.objects.defer("large_text_field")
```

Deferred fields are fetched lazily on attribute access — often a footgun if you then loop over records.

### Annotations and aggregations
```python
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField

orders = Order.objects.annotate(
    item_count=Count("items"),
    avg_price=Avg("items__price"),
    processing_time=ExpressionWrapper(
        F("completed_at") - F("created_at"),
        output_field=DurationField()
    )
)
```

### Q objects and complex filtering
```python
from django.db.models import Q

# OR queries:
User.objects.filter(Q(is_active=True) | Q(is_staff=True))

# NOT:
User.objects.filter(~Q(status="banned"))

# Dynamic filter building:
filters = Q()
if search_term:
    filters &= Q(name__icontains=search_term)
if active_only:
    filters &= Q(is_active=True)
qs = User.objects.filter(filters)
```

### F expressions (database-side computation)
```python
from django.db.models import F

# Increment without fetching (atomic):
Product.objects.filter(pk=pk).update(view_count=F("view_count") + 1)

# Compare two fields:
Order.objects.filter(delivered_at__lt=F("promised_at"))
```

### Subqueries
```python
from django.db.models import OuterRef, Subquery

latest_order = Order.objects.filter(
    user=OuterRef("pk")
).order_by("-created_at").values("total")[:1]

users = User.objects.annotate(latest_order_total=Subquery(latest_order))
```

### values() and values_list()
```python
# Returns dicts instead of model instances:
Order.objects.values("id", "status", "user__email")

# Returns tuples:
Order.objects.values_list("id", "status")

# Flat list of single field:
Order.objects.values_list("id", flat=True)
```

### bulk operations
```python
# bulk_create: one INSERT for many rows
Order.objects.bulk_create([
    Order(user=user, total=total) for user, total in data
], batch_size=500)

# bulk_update: one UPDATE for many rows
for order in orders:
    order.status = "shipped"
Order.objects.bulk_update(orders, ["status"], batch_size=500)
```

---

## PostgreSQL-specific features (django.contrib.postgres)

### Full-text search
```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

# Basic:
Article.objects.filter(body__search="django background tasks")

# Ranked with vector:
vector = SearchVector("title", weight="A") + SearchVector("body", weight="B")
query = SearchQuery("django tasks")
Article.objects.annotate(
    rank=SearchRank(vector, query)
).filter(rank__gte=0.1).order_by("-rank")
```

### Lexeme (new in Django 6.0)
`Lexeme` gives safer full-text query composition, especially when terms come from untrusted input.

```python
from django.contrib.postgres.search import SearchQuery, SearchVector, Lexeme

vector = SearchVector("title", weight="A") + SearchVector("body", weight="B")

Article.objects.annotate(search=vector).filter(
    search=SearchQuery(Lexeme("fruit") & Lexeme("dessert"))
)
```

`Lexeme` supports `&`, `|`, `~`, prefix matching, and weighting.

### JSON field operations
```python
# JSONField supports nested lookups natively:
Product.objects.filter(metadata__color="blue")
Product.objects.filter(metadata__dimensions__height__gte=10)

# Django 6.0: negative array indexing on SQLite (was Postgres-only):
Product.objects.filter(tags__-1="featured")
```

### ArrayField
```python
from django.contrib.postgres.fields import ArrayField

class Post(Model):
    tags = ArrayField(CharField(max_length=50), default=list)

# Queries:
Post.objects.filter(tags__contains=["django"])
Post.objects.filter(tags__overlap=["django", "python"])
Post.objects.filter(tags__len=3)
```

### HStoreField (key-value store in Postgres)
```python
from django.contrib.postgres.fields import HStoreField

class Product(Model):
    attributes = HStoreField()

Product.objects.filter(attributes__color="red")
```

### Range fields
```python
from django.contrib.postgres.fields import DateRangeField, NumericRangeField
from psycopg2.extras import DateRange

class Event(Model):
    date_range = DateRangeField()

Event.objects.filter(date_range__contains=date(2026, 3, 18))
Event.objects.filter(date_range__overlap=DateRange(start, end))
```

### Indexes
```python
from django.contrib.postgres.indexes import GinIndex, GistIndex, BrinIndex

class Article(Model):
    body = TextField()
    tags = ArrayField(CharField(max_length=50))

    class Meta:
        indexes = [
            GinIndex(fields=["tags"]),  # for ArrayField / JSONField overlap queries
            GinIndex(SearchVector("body"), name="body_fts_idx"),  # full-text
            BrinIndex(fields=["created_at"]),  # for large append-only tables
        ]
```

Also relevant for production Postgres work:

- partial indexes for highly selective subsets
- covering indexes via `Index(..., include=[...])` on PostgreSQL
- concurrent index operations for large tables, using PostgreSQL-specific migration operations instead of blocking table writes

### Constraints
```python
from django.db.models import CheckConstraint, UniqueConstraint, Q

class Product(Model):
    price = DecimalField(...)
    discount = DecimalField(...)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(price__gte=0) & Q(discount__lte=F("price")),
                name="valid_price_discount"
            ),
            UniqueConstraint(
                fields=["sku"],
                condition=Q(is_active=True),
                name="unique_active_sku"
            )
        ]
```

### select_for_update (row-level locking)
```python
with transaction.atomic():
    account = Account.objects.select_for_update().get(pk=pk)
    account.balance -= amount
    account.save()
```

`select_for_update(nowait=True)` raises `DatabaseError` instead of blocking. `skip_locked=True` skips locked rows (useful for queue-like patterns).

---

## Django 6.0 ORM-specific additions

### RETURNING clause optimization
On PostgreSQL, SQLite, and Oracle: after `save()`, `GeneratedField` values and fields assigned expressions are refreshed via a single `RETURNING` clause rather than a separate SELECT. No code changes needed — it's automatic.

### StringAgg on all backends
Previously PostgreSQL-only; now works on all Django-supported databases.

### AnyValue aggregate
Returns an arbitrary non-null value from a group. Useful when grouping but you don't care which specific value you get from non-grouped columns. Supported on PostgreSQL 16+, SQLite, MySQL, Oracle.

### Composite Primary Keys (from Django 5.2, expanded in 6.0)
```python
from django.db.models import CompositePrimaryKey

class OrderItem(Model):
    pk = CompositePrimaryKey("order_id", "product_id")
    order = ForeignKey(Order, on_delete=CASCADE)
    product = ForeignKey(Product, on_delete=CASCADE)

# Filter by composite PK:
OrderItem.objects.filter(pk=(order_id, product_id))

# In 6.0: subqueries with CompositePrimaryKey can target non-__in lookups:
OrderItem.objects.filter(pk__exact=(1, "A755H"))
```

### PostgreSQL checks and extension hints

- `django.contrib.postgres` fields, indexes, and constraints now include system checks to verify that `django.contrib.postgres` is installed.
- `CreateExtension` and related PostgreSQL operations now accept `hints` for database-router scenarios.

---

## Performance patterns

### Use `iterator()` for large querysets
```python
# Avoids loading entire queryset into memory:
for order in Order.objects.filter(status="pending").iterator(chunk_size=1000):
    process(order)
```

### Avoid N+1 with `annotate` instead of Python loops
```python
# Bad:
for user in users:
    user.order_count = user.orders.count()  # N queries

# Good:
users = User.objects.annotate(order_count=Count("orders"))
```

### explain() for query analysis
```python
print(Order.objects.filter(status="pending").explain(verbose=True, analyze=True))
# Prints PostgreSQL EXPLAIN ANALYZE output
```

## Production-sharp Postgres guidance

- Use JSONB when the shape is genuinely flexible; do not hide relational structure in JSON because it is convenient in the API layer.
- For high-write tables, be explicit about lock ordering and transaction scope to reduce deadlock risk.
- For large-table index creation, prefer concurrent operations so writes are not blocked during rollout.
- Reach for `select_for_update(skip_locked=True)` only when queue-like semantics are intentional and well understood.

---

## Migration best practices

- Always run `makemigrations --check` in CI to catch missing migrations.
- Use `RunSQL` with `reverse_sql` for custom DB operations.
- `SeparateDatabaseAndState` for zero-downtime column renames.
- For large tables: add columns with `null=True` first, backfill, then add constraints.

## Sources

- Django 6.0 release notes: https://docs.djangoproject.com/en/6.0/releases/6.0/
- PostgreSQL full-text search docs: https://docs.djangoproject.com/en/6.0/ref/contrib/postgres/search/
- `django.contrib.postgres` docs: https://docs.djangoproject.com/en/6.0/ref/contrib/postgres/

Last updated: 2026-03-18
