---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [django, testing, factory_boy, pytest, celery, freezegun]
related:
  - django-migrations-advanced.md
  - django-orm-postgres.md
  - django-6.0-whats-new.md
---

# Django Test Data: factory_boy, freezegun, and Mocking Patterns

## Why factory_boy

`factory_boy` replaces hand-rolled fixtures and `Model.objects.create(...)` chains. Key benefits: factories only declare the fields they care about (overriding defaults per-test), they compose via SubFactory/RelatedFactory, and they integrate cleanly with `pytest-django`. Current stable version is 3.3.x.

```bash
pip install factory-boy  # includes Faker
```

---

## DjangoModelFactory basics

```python
# factories.py
import factory
from factory.django import DjangoModelFactory
from myapp.models import User, Article, Tag

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
```

`factory.Sequence` guarantees uniqueness across tests. `factory.LazyAttribute` computes from other declared fields — `o` is the object under construction. `factory.Faker` delegates to the `Faker` library.

### Build strategies

```python
# create() — saves to DB (uses Model.objects.create())
user = UserFactory()               # same as UserFactory.create()

# build() — in-memory only, no DB hit
user = UserFactory.build()

# create_batch / build_batch
users = UserFactory.create_batch(5)
users = UserFactory.build_batch(5, is_active=False)

# Override any field on the fly
user = UserFactory(email='custom@example.com')
```

---

## Faker integration

`factory.Faker` wraps the `Faker` library. Any Faker provider method works:

```python
class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    bio = factory.Faker('paragraph', nb_sentences=3)
    avatar_url = factory.Faker('image_url', width=200, height=200)
    city = factory.Faker('city')
    country_code = factory.Faker('country_code')
    date_of_birth = factory.Faker('date_of_birth', minimum_age=18, maximum_age=65)
```

### Seeding for reproducibility

```python
# In conftest.py or the test itself
factory.random.reseed_random(42)
```

---

## SubFactory — foreign key relationships

```python
class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article

    author = factory.SubFactory(UserFactory)
    title = factory.Faker('sentence', nb_words=6)
    body = factory.Faker('text', max_nb_chars=1000)
    status = 'draft'
```

SubFactory creates the related object before the parent. Override by passing an existing instance:

```python
user = UserFactory()
article = ArticleFactory(author=user)
```

---

## LazyAttribute and LazyFunction

```python
class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article

    title = factory.Faker('sentence', nb_words=5)
    # slug derived from title at build time
    slug = factory.LazyAttribute(lambda o: o.title.lower().replace(' ', '-')[:50])
    # published_at only set when status is 'published'
    published_at = factory.LazyFunction(timezone.now)
```

`LazyFunction` is for callables with no dependency on other fields. `LazyAttribute` receives `o`, the factory object under construction.

---

## Traits — conditional field groups

Traits let you flip a named set of field overrides:

```python
class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article

    status = 'draft'
    published_at = None

    class Params:
        published = factory.Trait(
            status='published',
            published_at=factory.LazyFunction(timezone.now),
        )
        archived = factory.Trait(
            status='archived',
        )
```

```python
draft = ArticleFactory()                   # status='draft'
pub = ArticleFactory(published=True)       # status='published', published_at set
arch = ArticleFactory(archived=True)       # status='archived'
```

---

## @factory.post_generation — ManyToMany and post-save hooks

Django M2M relationships can't be set before the object is saved:

```python
class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return  # build() strategy — skip M2M
        if extracted:
            # explicit: ArticleFactory(tags=[tag1, tag2])
            self.tags.set(extracted)
        else:
            # default: assign 2 random tags
            self.tags.set(TagFactory.create_batch(2))
```

```python
# Use it:
article = ArticleFactory()                           # 2 random tags
article = ArticleFactory(tags=[])                    # no tags (falsy extracted)
tag = TagFactory()
article = ArticleFactory(tags=[tag])                 # specific tag
```

The `extracted` arg receives whatever was passed as the kwarg. A key subtlety: passing an empty list `tags=[]` is falsy, so the default branch runs — guard against this if needed with `if extracted is not None`.

---

## RelatedFactory — reverse FK / post-save creation

When you need to create related objects *after* the parent is saved (e.g., a Profile that OneToOne-links to User):

```python
class UserWithProfileFactory(DjangoModelFactory):
    class Meta:
        model = User

    profile = factory.RelatedFactory(
        ProfileFactory,
        factory_related_name='user',  # the FK field name on Profile pointing to User
    )
```

`RelatedFactory` creates the related object after the parent, setting the FK automatically.

---

## Patterns for tricky model shapes

### unique_together

Use `Sequence` on the unique combination:

```python
class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    user = factory.SubFactory(UserFactory)
    day = factory.Sequence(lambda n: date(2024, 1, 1) + timedelta(days=n))
    # user + day is unique_together — Sequence ensures different days per user
```

### Self-referential models

```python
class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Faker('word')
    parent = None  # top-level by default

class SubcategoryFactory(CategoryFactory):
    parent = factory.SubFactory(CategoryFactory)
```

### Abstract base / multi-table inheritance

Subclass the parent factory and set `model` in the child's `Meta`. factory_boy handles multi-table inheritance correctly — it calls `Model.objects.create()` on the concrete child model.

---

## Database state isolation in pytest

```python
# conftest.py
import pytest

@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture
def published_article(db, user):
    return ArticleFactory(author=user, published=True)
```

### `@pytest.mark.django_db` and the `db` fixture

| Fixture / mark | Wraps in transaction | Rolls back after |
|---|---|---|
| `@pytest.mark.django_db` | ✅ | ✅ per test |
| `@pytest.mark.django_db(transaction=True)` | ❌ | flushes DB |
| `db` fixture | same as mark | same |
| `django_db_setup` | one-time DB setup | no |

Use `transaction=True` only when your code path uses `transaction.on_commit()` (e.g., triggering Celery tasks) — otherwise the default savepoint-based isolation is faster.

### `--reuse-db` (pytest-django)

`pytest --reuse-db` skips migrations on subsequent runs. Factories remain unaffected — they create data fresh each test. The `--create-db` flag forces a rebuild.

---

## Mocking Celery tasks in tests

### Option 1: `CELERY_TASK_ALWAYS_EAGER` (legacy, avoid in new code)

```python
# settings_test.py
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

Tasks run synchronously in the same thread. Deprecated approach — prefer `celery.contrib.pytest`.

### Option 2: `celery.contrib.pytest` fixtures (recommended)

```bash
pip install celery[pytest]
```

```python
# conftest.py
@pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
    }
```

In tests:

```python
@pytest.mark.django_db(transaction=True)  # needed for on_commit to fire
def test_export_triggers_task(user, celery_worker):
    # celery_worker fixture spins up a real in-process worker
    result = trigger_export_task.delay(user.id)
    result.get(timeout=5)
    assert Export.objects.filter(user=user).exists()
```

The `celery_app` fixture gives you the configured app; `celery_worker` spins up an actual worker thread — use it only for integration tests. For unit tests, call `.apply()` directly:

```python
def test_send_welcome_email(mailoutbox):
    result = send_welcome_email.apply(args=[user.id])
    assert result.successful()
    assert len(mailoutbox) == 1
```

### Option 3: `unittest.mock.patch` (fastest, for unit tests)

```python
from unittest.mock import patch

def test_article_publish_queues_notification(db):
    article = ArticleFactory(status='draft')
    with patch('myapp.tasks.send_publication_notification.delay') as mock_delay:
        article.publish()
        mock_delay.assert_called_once_with(article.id)
```

This is the right choice when you want to test that a task was called with the right arguments without actually running the task. Combine with `assert_called_once_with` / `call_args` to be precise.

---

## freezegun — controlling time in tests

```bash
pip install freezegun
```

### Decorator form

```python
from freezegun import freeze_time
from django.utils import timezone

@freeze_time('2025-06-15 12:00:00')
def test_article_appears_in_published_today_feed(db):
    article = ArticleFactory(published=True, published_at=timezone.now())
    feed = Article.objects.published_today()
    assert article in feed
```

### Context manager form

```python
def test_subscription_expires(db, subscription):
    with freeze_time('2025-12-31 23:59:59'):
        assert not subscription.is_expired()
    with freeze_time('2026-01-01 00:00:01'):
        assert subscription.is_expired()
```

### Freezing inside Celery tasks

freezegun patches `datetime.datetime` globally. When tasks run in the same thread (`.apply()`), freezegun works naturally. With `celery_worker` (separate thread), you need to pass the freeze into the task or assert on side effects rather than timestamps:

```python
@freeze_time('2025-06-15')
def test_daily_digest_uses_correct_date(db, celery_app):
    result = generate_daily_digest.apply()
    digest = Digest.objects.latest('created_at')
    # Check the result, not the internal timestamp
    assert digest.date == date(2025, 6, 15)
```

### Interaction with `django.utils.timezone`

freezegun correctly patches `django.utils.timezone.now()` when `USE_TZ = True`. No special configuration needed — timezone-aware comparisons work as expected under the freeze.

---

## responses — mocking outbound HTTP

Use `responses` (or `httpretty`) to mock external HTTP calls made from views or tasks:

```bash
pip install responses
```

```python
import responses as resp

@resp.activate
def test_stripe_webhook_handled(db, client):
    resp.add(
        resp.POST,
        'https://api.stripe.com/v1/charges',
        json={'id': 'ch_test_123', 'status': 'succeeded'},
        status=200,
    )
    response = client.post('/webhooks/stripe/', data={...}, content_type='application/json')
    assert response.status_code == 200
```

### pytest decorator form

```python
@pytest.mark.django_db
@resp.activate
def test_geocoding_task(user):
    resp.add(resp.GET, 'https://maps.example.com/geocode', json={'lat': 37.7, 'lon': -122.4})
    result = geocode_user_address.apply(args=[user.id])
    assert result.successful()
```

### `responses` passthrough for real calls

```python
resp.add_passthrough('http://localhost')  # still allow local URLs
```

---

## Putting it together: a realistic test module

```python
# tests/test_article_publish.py
import pytest
from unittest.mock import patch
from freezegun import freeze_time
from .factories import UserFactory, ArticleFactory

@pytest.mark.django_db
@freeze_time('2025-06-15 10:00:00')
def test_publish_sets_timestamp_and_queues_notification(db):
    article = ArticleFactory(status='draft')

    with patch('myapp.tasks.send_publication_notification.delay') as mock_delay:
        article.publish()

    article.refresh_from_db()
    assert article.status == 'published'
    assert article.published_at.date() == date(2025, 6, 15)
    mock_delay.assert_called_once_with(article.id)


@pytest.mark.django_db
def test_article_requires_author(db):
    # build() strategy — no DB hit, tests validation only
    article = ArticleFactory.build(author=None)
    with pytest.raises(ValidationError):
        article.full_clean()
```

---

## Key rules of thumb

- Prefer `build()` for validation tests; reserve `create()` for tests that need DB queries.
- Use `SubFactory` instead of creating objects manually inside tests — keeps factories composable and tests short.
- Don't reach for `celery_worker` unless you need integration-level assurance; `.apply()` + `mock.patch` cover 90% of Celery test needs.
- Pin `freeze_time` to explicit timestamps with timezone info when `USE_TZ = True` to avoid ambiguity.
- One factory file per app is fine; split only when a single file exceeds ~300 lines.
