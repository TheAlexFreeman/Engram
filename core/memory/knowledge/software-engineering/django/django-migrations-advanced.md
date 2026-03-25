---
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - django-orm-postgres.md
  - django-production-stack.md
  - django-database-pooling.md
  - django-6.0-whats-new.md
  - psycopg3-and-connection-management.md
  - django-security.md
  - drf-testing-pytest-django-perf-rec.md
origin_session: unknown
---

# Django Migrations — Advanced Patterns

The basics of migrations (generating, running, reverting) are covered in `django-orm-postgres.md`. This file covers the production-critical advanced topics: data migrations, zero-downtime deployment patterns, squashing, and handling large tables.

---

## 1. RunPython data migrations

Data migrations transform existing data — filling new columns, normalizing values, splitting or merging fields.

### The correct pattern

```python
# migrations/0042_populate_full_name.py
from django.db import migrations

def populate_full_name(apps, schema_editor):
    # Always use apps.get_model() — never import models directly.
    # The migration's model snapshot may differ from the current model class.
    User = apps.get_model("auth", "User")
    for user in User.objects.iterator():
        user.full_name = f"{user.first_name} {user.last_name}".strip()
        user.save(update_fields=["full_name"])

def reverse_populate_full_name(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.update(full_name="")

class Migration(migrations.Migration):
    dependencies = [("myapp", "0041_user_add_full_name")]

    operations = [
        migrations.RunPython(populate_full_name, reverse_populate_full_name),
    ]
```

**Critical rule**: always use `apps.get_model()`, never `from myapp.models import User`. Direct imports use the current model definition, which may have fields or methods that don't exist at the time this migration runs. This causes hard-to-debug failures when running migrations on a fresh database.

### Batching for large tables

```python
def populate_full_name(apps, schema_editor):
    User = apps.get_model("auth", "User")
    batch_size = 1000
    qs = User.objects.filter(full_name="").order_by("id")
    
    while True:
        batch = list(qs[:batch_size])
        if not batch:
            break
        for user in batch:
            user.full_name = f"{user.first_name} {user.last_name}".strip()
        User.objects.bulk_update(batch, ["full_name"])
```

`bulk_update` issues a single SQL statement per batch — vastly faster than individual `.save()` calls.

### Disabling transaction wrapping

```python
class Migration(migrations.Migration):
    atomic = False  # RunPython will NOT be wrapped in a transaction

    operations = [
        migrations.RunPython(populate_full_name, migrations.RunPython.noop, atomic=False),
    ]
```

Use `atomic=False` when:
- The migration takes so long that holding a transaction open would cause issues
- You need `CREATE INDEX CONCURRENTLY` (`AddIndexConcurrently` automatically uses this)
- You want partial progress to persist if the migration is interrupted

---

## 2. SeparateDatabaseAndState — zero-downtime renames

`SeparateDatabaseAndState` lets you apply a different operation to the database vs. to Django's migration state. This is the cornerstone of zero-downtime schema changes.

### Safe field rename (three-deploy pattern)

**Goal**: rename `first_name` → `given_name`.

**Deploy 1 — Add new column, keep old column**
```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddField("User", "given_name", models.CharField(max_length=50, blank=True)),
    ]
```

**Deploy 1 code**: write to both `first_name` and `given_name`, read from `first_name`.

**Backfill data** (via management command or `RunPython` migration):
```python
User.objects.update(given_name=F("first_name"))
```

**Deploy 2 — Switch reads to new column**

Code now reads from `given_name` (it's fully populated). Still write to both columns to support rollback.

**Deploy 3 — Drop old column**
```python
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField("User", "first_name"),
    ]
```

### Model rename using SeparateDatabaseAndState

```python
class Migration(migrations.Migration):
    operations = [
        # Tell Django's state that we renamed the model...
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel("OldName", "NewName"),
            ],
            # ...but don't touch the actual database table
            database_operations=[],
        ),
    ]
```

Then in a separate deploy, after all FK references are updated and the rename is stable, actually rename the table:

```python
database_operations=[
    migrations.RunSQL(
        "ALTER TABLE myapp_oldname RENAME TO myapp_newname",
        reverse_sql="ALTER TABLE myapp_newname RENAME TO myapp_oldname",
    ),
]
```

---

## 3. Squashing migrations

Over time, migration files accumulate. Squashing reduces N migrations into one without recreating the database from scratch.

### The squash command

```bash
python manage.py squashmigrations myapp 0001 0042
```

This creates `0001_squashed_0042_...py`. It:
- Contains the net operations (additions and removals cancel out)
- Has a `replaces` attribute listing all squashed migrations

### What squash does and doesn't do

- **Does**: create a single file that's equivalent to running migrations 0001–0042 on a fresh database
- **Does not**: alter anything on existing databases  
- **Does not**: automatically delete the old migration files

### The safe cleanup flow

1. Generate the squash file
2. Test: `python manage.py migrate --run-syncdb` on a fresh database; verify the squash works
3. Deploy the squash file (with old files still present); Django detects that existing databases have run the old migrations and skips them
4. After all environments have the squash applied, delete the old migration files (0001–0042) and remove the `replaces` attribute from the squash file
5. Rename the squash file to `0001_initial.py`

**Key risk**: deleting old migration files prematurely breaks any environment that hasn't yet migrated to 0042.

---

## 4. Zero-downtime migration patterns

The core rule: **schema migrations and code deploys are separate, ordered steps**. During a rolling deploy, the old code and new code must both be able to run against the same schema simultaneously.

### Adding a column safely

```python
# Safe: nullable or with default
migrations.AddField(
    "Order",
    "shipped_at",
    models.DateTimeField(null=True, blank=True),
)
# Or with a database-level default (Django 5.0+):
models.DateTimeField(default=None, db_default=Now())
```

Adding a NOT NULL column without a default requires a table rewrite in Postgres (locks the table). Always add nullable first, backfill, then add the NOT NULL constraint.

### Removing a column safely (two-deploy)

1. **Deploy 1**: stop referencing the column in code (`exclude_fields`, remove from serializers/forms). Run migration with `RemoveField` to drop at database level — *after* the code no longer reads or writes the field.
2. Or more cautiously: use `SeparateDatabaseAndState` to remove the column from Django's model state first, then drop the database column in a follow-up migration.

### Adding a NOT NULL constraint after backfill

```python
# After backfilling all rows:
migrations.AlterField(
    "Order",
    "shipped_at",
    models.DateTimeField(null=False),  # causes table rewrite in old Postgres behavior
)
# Better: use SET NOT NULL with a check constraint first (Postgres 12+ validation)
migrations.RunSQL(
    "ALTER TABLE orders ALTER COLUMN shipped_at SET NOT NULL",
    reverse_sql="ALTER TABLE orders ALTER COLUMN shipped_at DROP NOT NULL",
)
```

---

## 5. Fake migrations

### Legitimate uses

```bash
# Mark a migration as applied without running it
python manage.py migrate myapp 0042 --fake

# Initial migration on an existing database (tables already exist)
python manage.py migrate --fake-initial
```

`--fake-initial` is safe on fresh databases: Django checks whether the tables listed in the migration already exist. If they do, it marks as applied. If not, it runs the migration. This is standard practice when adding migrations to a database that was created outside of Django migrations.

### Dangerous use

Using `--fake` to skip a broken migration and then fixing data manually is occasionally necessary, but:
- Always document it in the migration with a comment
- Record the manual SQL applied as a comment in the faked migration
- Never fake migrations in automated CI/CD pipelines

---

## 6. Migration conflicts (concurrent branches)

When two branches both add migrations from the same parent, you get a conflict:

```
myapp/
  0041_add_field_x.py   # branch A
  0041_add_field_y.py   # branch B — conflict!
```

### Resolving

```bash
python manage.py makemigrations --merge myapp
```

This creates `0042_merge_....py` with both 0041s as dependencies. Review the merge migration to verify the operations are compatible.

**Prevention**: in teams, coordinate migration numbering or use a branch-specific prefix convention during development and renumber for merge.

---

## 7. Large table migrations

For tables with millions of rows, standard Django migrations can lock the table for minutes.

### AddIndexConcurrently

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # concurrent operations cannot run in a transaction

    operations = [
        AddIndexConcurrently(
            "Order",
            models.Index(fields=["created_at"], name="order_created_at_idx"),
        ),
    ]
```

`AddIndexConcurrently` maps to `CREATE INDEX CONCURRENTLY` — which builds the index without locking reads or writes (though it takes longer and uses more CPU).

### django-pg-zero-downtime

For all lock-sensitive operations (NOT NULL constraints, column type changes):

```bash
pip install django-pg-zero-downtime
```

```python
# settings.py
ZERO_DOWNTIME_MIGRATIONS_LOCK_TIMEOUT = "2s"
ZERO_DOWNTIME_MIGRATIONS_STATEMENT_TIMEOUT = "2s"
ZERO_DOWNTIME_MIGRATIONS_RAISE_IF_NOT_ZERO_DOWNTIME = True  # fail if an operation would lock
```

The package replaces standard migration operations with Postgres-compatible equivalents that avoid table-level locks: adding columns uses `DEFAULT` + backfill trick, adding constraints uses `NOT VALID` + `VALIDATE CONSTRAINT`.

### pg_repack

For bloated tables (after many updates/deletes) that need a full rewrite without downtime:

```bash
# System package or extension
CREATE EXTENSION pg_repack;
pg_repack --table myapp_order --jobs 4
```

`pg_repack` rebuilds the table in the background, swapping it in with minimal locking at the end. Different from migrations — it's a maintenance operation run outside of Django.

---

## 8. Testing migrations

### Data migration tests

```python
# tests/test_migrations.py
import pytest
from django.test import TestCase

class TestPopulateFullName(TestCase):
    @pytest.mark.django_db
    def test_forward_migration(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        # Create user via the "old" state
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create(first_name="John", last_name="Doe", username="jdoe",
                            full_name="")
        
        # Call the migration function directly
        from myapp.migrations.0042_populate_full_name import populate_full_name
        from django.apps import apps
        populate_full_name(apps, connection.schema_editor())
        
        user = User.objects.get(username="jdoe")
        assert user.full_name == "John Doe"
```

### Detecting missing migrations in CI

```bash
python manage.py makemigrations --check --dry-run
```

Returns exit code 1 if any model changes are not covered by a migration. Add to CI:

```yaml
- run: python manage.py makemigrations --check --dry-run
```

### Testing migration reversibility

```python
from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

class ReverseMigrationTest(TestCase):
    def test_reverse(self):
        executor = MigrationExecutor(connection)
        # Migrate back to before our migration
        executor.migrate([("myapp", "0041_previous")])
        # Check state is correct
        # Migrate forward again
        executor.migrate([("myapp", "0042_our_migration")])
```
