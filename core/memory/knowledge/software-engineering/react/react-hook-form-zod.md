---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [react, forms, react-hook-form, zod, validation, chakra-ui, drf]
version_note: react-hook-form v7, @hookform/resolvers v5, zod v3 (zod v4 resolver in progress as of mid-2025)
related:
  - react-performance.md
  - react-19-overview.md
  - react-error-boundaries-suspense.md
  - vite-react-build.md
---

# react-hook-form + zod — Performant Type-Safe Forms

## Why this combination

`react-hook-form` keeps forms uncontrolled (fields don't re-render the parent on every keystroke), making it the performant default. `zod` provides TypeScript-first schema validation with rich inference — the same schema can validate the form and type the API payload. `@hookform/resolvers/zod` bridges them.

```bash
npm install react-hook-form zod @hookform/resolvers
```

---

## Basic setup

```tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const schema = z.object({
  title: z.string().min(1, 'Title is required').max(200),
  body: z.string().min(10, 'Body must be at least 10 characters'),
  status: z.enum(['draft', 'published']),
})

type ArticleFormData = z.infer<typeof schema>  // TypeScript type from schema

function ArticleForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty, isValid },
    reset,
    watch,
    setValue,
    setError,
  } = useForm<ArticleFormData>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', body: '', status: 'draft' },
    mode: 'onBlur',  // validate on blur; alternatives: 'onChange', 'onSubmit'
  })

  const onSubmit = async (data: ArticleFormData) => {
    try {
      await createArticle(data)
      reset()
    } catch (error) {
      // Map DRF errors back to fields (see DRF section below)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('title')} />
      {errors.title && <p>{errors.title.message}</p>}

      <textarea {...register('body')} />
      {errors.body && <p>{errors.body.message}</p>}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving...' : 'Save'}
      </button>
    </form>
  )
}
```

### Validation modes

| `mode` | When validation runs |
|---|---|
| `'onSubmit'` (default) | Only on submit attempt |
| `'onBlur'` | On field blur (good UX default) |
| `'onChange'` | On every keystroke (expensive, avoid for large forms) |
| `'onTouched'` | First on blur, then on change after first blur |
| `'all'` | Blur and change |

---

## formState — the key flags

```tsx
const { formState: { errors, isSubmitting, isDirty, isValid, touchedFields, dirtyFields } } = useForm(...)
```

| Flag | Meaning |
|---|---|
| `errors` | Current validation errors per field |
| `isSubmitting` | `handleSubmit` async function is running |
| `isDirty` | Any field differs from `defaultValues` |
| `isValid` | No current validation errors |
| `touchedFields` | Fields the user has interacted with |
| `dirtyFields` | Only the fields that have changed |

**Performance note**: `formState` is proxied — accessing a property subscribes to it. Don't destructure the whole object; only destructure what you use.

---

## Controller — Chakra UI integration

Chakra UI components are controlled (they manage their own value). `register()` doesn't work with them; use `<Controller>`:

```tsx
import { Controller } from 'react-hook-form'
import { Input, Select, Checkbox, FormControl, FormLabel, FormErrorMessage } from '@chakra-ui/react'

function ArticleForm() {
  const { control, handleSubmit, formState: { errors } } = useForm<ArticleFormData>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', status: 'draft', notify: false },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Text input with Chakra */}
      <FormControl isInvalid={!!errors.title}>
        <FormLabel>Title</FormLabel>
        <Controller
          name="title"
          control={control}
          render={({ field }) => <Input {...field} />}
        />
        <FormErrorMessage>{errors.title?.message}</FormErrorMessage>
      </FormControl>

      {/* Select */}
      <FormControl isInvalid={!!errors.status}>
        <FormLabel>Status</FormLabel>
        <Controller
          name="status"
          control={control}
          render={({ field }) => (
            <Select {...field}>
              <option value="draft">Draft</option>
              <option value="published">Published</option>
            </Select>
          )}
        />
        <FormErrorMessage>{errors.status?.message}</FormErrorMessage>
      </FormControl>

      {/* Checkbox */}
      <Controller
        name="notify"
        control={control}
        render={({ field: { value, onChange, ...rest } }) => (
          <Checkbox isChecked={value} onChange={e => onChange(e.target.checked)} {...rest}>
            Notify subscribers
          </Checkbox>
        )}
      />
    </form>
  )
}
```

**Pattern**: `field` from `render` contains `value`, `onChange`, `onBlur`, `ref`, `name`. Spread it onto native inputs; for Chakra, adapt `value`/`onChange` to match the component's expected API.

---

## useFormContext and FormProvider — multi-part forms

Avoid prop-drilling `control` / `register` through deep component trees:

```tsx
import { FormProvider, useFormContext } from 'react-hook-form'

// Top-level — wraps the whole form
function ArticleEditor() {
  const methods = useForm<ArticleFormData>({ resolver: zodResolver(schema) })
  return (
    <FormProvider {...methods}>
      <form onSubmit={methods.handleSubmit(onSubmit)}>
        <TitleSection />
        <BodySection />
        <MetaSection />
        <SubmitButton />
      </form>
    </FormProvider>
  )
}

// Any nested component — no props needed
function TitleSection() {
  const { register, formState: { errors } } = useFormContext<ArticleFormData>()
  return (
    <FormControl isInvalid={!!errors.title}>
      <Input {...register('title')} />
      <FormErrorMessage>{errors.title?.message}</FormErrorMessage>
    </FormControl>
  )
}
```

---

## useFieldArray — dynamic lists

```tsx
import { useFieldArray } from 'react-hook-form'

const schema = z.object({
  authors: z.array(z.object({
    name: z.string().min(1),
    email: z.string().email(),
  })).min(1, 'At least one author is required'),
})

function AuthorsField() {
  const { control, register, formState: { errors } } = useFormContext<FormData>()
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: 'authors',
  })

  return (
    <>
      {fields.map((field, index) => (
        <div key={field.id}>  {/* Always use field.id, not index, as key */}
          <input {...register(`authors.${index}.name`)} defaultValue={field.name} />
          <input {...register(`authors.${index}.email`)} defaultValue={field.email} />
          {errors.authors?.[index]?.name && (
            <p>{errors.authors[index].name.message}</p>
          )}
          <button type="button" onClick={() => remove(index)}>Remove</button>
        </div>
      ))}
      <button type="button" onClick={() => append({ name: '', email: '' })}>
        Add author
      </button>
      {errors.authors?.root && <p>{errors.authors.root.message}</p>}
    </>
  )
}
```

`field.id` is a stable UUID assigned by RHF — always use it as the `key`, not `index`.

---

## Zod schema patterns

### Common validators

```ts
const schema = z.object({
  // Strings
  title: z.string().min(1).max(200).trim(),
  slug: z.string().regex(/^[a-z0-9-]+$/, 'Lowercase letters, numbers, and hyphens only'),
  email: z.string().email(),
  url: z.string().url().optional(),

  // Numbers (form inputs are strings by default — coerce)
  price: z.coerce.number().min(0).max(10_000),
  quantity: z.coerce.number().int().positive(),

  // Enums
  status: z.enum(['draft', 'published', 'archived']),
  priority: z.union([z.literal(1), z.literal(2), z.literal(3)]),

  // Nullable vs optional
  parent_id: z.number().nullable(),   // can be null (but must be present)
  notes: z.string().optional(),        // can be absent from the object

  // Dates
  publish_at: z.string().datetime().optional(),

  // Booleans from checkboxes
  agreed: z.boolean().refine(v => v === true, 'You must agree'),
})
```

### .refine() — cross-field validation

```ts
const schema = z.object({
  password: z.string().min(8),
  confirm_password: z.string(),
}).refine(
  data => data.password === data.confirm_password,
  {
    message: "Passwords don't match",
    path: ['confirm_password'],  // which field the error appears on
  }
)
```

### .superRefine() — multiple errors from one validator

```ts
const schema = z.object({
  username: z.string(),
}).superRefine(async (data, ctx) => {
  const exists = await checkUsernameExists(data.username)
  if (exists) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Username is already taken',
      path: ['username'],
    })
  }
})
```

### .transform() — coerce before validation

```ts
// Tags as a comma-separated string → array
const schema = z.object({
  tags_input: z.string().transform(s => s.split(',').map(t => t.trim()).filter(Boolean)),
})
```

### Discriminated unions — conditional fields

```ts
const schema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('email'), email: z.string().email() }),
  z.object({ type: z.literal('phone'), phone: z.string().min(10) }),
])
```

The discriminated union gives better TypeScript narrowing and error messages than a plain `z.union`.

---

## Async field validation

For server-side checks (username availability, email uniqueness):

```tsx
const { register } = useForm<FormData>({
  resolver: zodResolver(schema),
})

// Attach async validate to a specific field
<input
  {...register('username', {
    validate: async value => {
      const taken = await checkUsername(value)
      return taken ? 'Username is already taken' : true
    },
  })}
/>
```

Or use `superRefine` on the zod schema (requires async resolver support — works fine with `zodResolver`).

**Debounce async validation**: React Hook Form doesn't debounce by default. Use `mode: 'onBlur'` or manually debounce inside `validate`:

```ts
const debouncedCheck = debounce(checkUsername, 400)
validate: async value => {
  const taken = await debouncedCheck(value)
  return taken ? 'Username is taken' : true
}
```

---

## DRF error mapping

DRF returns validation errors as `{ field_name: ["Error message."], non_field_errors: ["..."] }`:

```tsx
import { useMutation } from '@tanstack/react-query'
import { AxiosError } from 'axios'

function ArticleForm() {
  const { setError } = useForm<ArticleFormData>({ resolver: zodResolver(schema) })

  const { mutate } = useMutation({
    mutationFn: (data: ArticleFormData) => apiClient.post('/articles/', data),
    onError: (error: AxiosError<Record<string, string[]>>) => {
      const fieldErrors = error.response?.data
      if (!fieldErrors) return

      Object.entries(fieldErrors).forEach(([field, messages]) => {
        if (field === 'non_field_errors') {
          // Map to root error
          setError('root', { message: messages.join(' ') })
        } else {
          setError(field as keyof ArticleFormData, {
            type: 'server',
            message: messages.join(' '),
          })
        }
      })
    },
  })

  return (
    <form onSubmit={handleSubmit(data => mutate(data))}>
      {errors.root && <Alert status="error">{errors.root.message}</Alert>}
      {/* fields... */}
    </form>
  )
}
```

---

## Multi-step forms

```tsx
const STEPS = ['basics', 'content', 'meta'] as const
type Step = (typeof STEPS)[number]

// Subschemas — validate only the current step's fields
const stepSchemas = {
  basics: schema.pick({ title: true, slug: true }),
  content: schema.pick({ body: true }),
  meta: schema.pick({ status: true, publish_at: true }),
}

function MultiStepArticleForm() {
  const [step, setStep] = useState<Step>('basics')
  const methods = useForm<ArticleFormData>({
    resolver: zodResolver(schema),   // full schema for final submit
    mode: 'onBlur',
  })

  const handleNext = async () => {
    // Validate only the fields relevant to the current step
    const valid = await methods.trigger(Object.keys(stepSchemas[step]) as any)
    if (valid) setStep(STEPS[STEPS.indexOf(step) + 1])
  }

  return (
    <FormProvider {...methods}>
      {step === 'basics' && <BasicsStep />}
      {step === 'content' && <ContentStep />}
      {step === 'meta' && <MetaStep />}
      <button onClick={handleNext}>Next</button>
    </FormProvider>
  )
}
```

`methods.trigger(fieldNames)` runs validation for a subset of fields — the right tool for per-step validation without a full submit.

---

## watch and setValue — reactive reads and writes

```tsx
// Watch a single field — re-renders component when it changes
const status = watch('status')

// Watch everything (expensive — avoid unless needed)
const allValues = watch()

// Programmatic update — does NOT trigger validation by default
setValue('slug', slugify(titleValue))

// Update and trigger validation
setValue('slug', slugify(titleValue), { shouldValidate: true, shouldDirty: true })
```

Prefer `watch` over `getValues` when you need the component to react to changes. Use `getValues` for reading values inside event handlers without causing re-renders.

---

## reset — pre-populating edit forms

```tsx
// Editing an existing article — populate form from fetched data
const { data: article } = useQuery({ queryKey: articleKeys.detail(id), queryFn: () => fetchArticle(id) })

useEffect(() => {
  if (article) {
    reset({
      title: article.title,
      body: article.body,
      status: article.status,
    })
  }
}, [article, reset])
```

Calling `reset(values)` both sets values and resets `isDirty` / `touchedFields` — so the user starts from a clean baseline matching the server state.

---

## Key rules of thumb

- Use `register` for plain HTML inputs; use `<Controller>` for any Chakra UI (or other controlled) component.
- Let zod own the type — always `type FormData = z.infer<typeof schema>`, never hand-write the type.
- Set `mode: 'onBlur'` as your default; only upgrade to `'onChange'` for fields that really benefit from live feedback (passwords, username availability).
- Don't use `watch()` without arguments — scope it to specific fields to avoid unnecessary re-renders.
- Map DRF field errors explicitly on mutation failure using `setError` — never silently swallow server validation errors.
- Use `methods.trigger(fields)` for per-step validation in multi-step flows; don't create a new `useForm` per step.
