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
  - react-hook-form-zod.md
  - tanstack-router.md
  - ../web-fundamentals/javascript-core-patterns.md
---

# TypeScript Patterns for React

TypeScript in React most often trips on three things: getting props right across composition boundaries, keeping API types aligned with runtime data, and avoiding the subtle ref/context typing traps. This file covers the practical patterns — what to reach for and what to avoid.

---

## 1. Component prop typing

### Prefer plain function over React.FC

```typescript
// ❌ React.FC — adds implicit children, can't use generics cleanly
const Button: React.FC<ButtonProps> = ({ children, onClick }) => ...

// ✅ Plain function — explicit, no implicit children, works with generics
function Button({ children, onClick }: ButtonProps) { ... }
```

`React.FC` was more useful in older React where children weren't typed. Since React 18, children must be explicit. Plain functions are more readable and don't fight TypeScript generics.

### ReactNode vs. ReactElement

```typescript
type CardProps = {
  // ReactNode: anything renderable — string, number, element, array, null, boolean
  children: React.ReactNode;
  
  // ReactElement: a JSX element specifically (not string/null)
  icon: React.ReactElement;
  
  // ComponentType: a component function/class (used when passing components as props)
  EmptyState: React.ComponentType<{ message: string }>;
};
```

### PropsWithChildren

```typescript
// Equivalent: type WrapperProps = { title: string; children: React.ReactNode }
type WrapperProps = React.PropsWithChildren<{ title: string }>;
```

Useful for pure wrapper components where children is the main payload.

### Extending native element props

When building a component that wraps a native element, extend its props so all native attributes pass through:

```typescript
// ComponentPropsWithoutRef — doesn't expose ref (most common for functional wrappers)
type ButtonProps = React.ComponentPropsWithoutRef<"button"> & {
  variant?: "primary" | "secondary";
  isLoading?: boolean;
};

function Button({ variant = "primary", isLoading, children, ...rest }: ButtonProps) {
  return (
    <button {...rest} disabled={isLoading || rest.disabled}>
      {isLoading ? <Spinner /> : children}
    </button>
  );
}
// Now Button accepts all native button props: onClick, type, disabled, aria-*, data-*, etc.
```

For components that need to forward refs:

```typescript
// ComponentPropsWithRef — includes the ref prop
type InputProps = React.ComponentPropsWithRef<"input"> & {
  label: string;
};
```

---

## 2. Generic components

### Generic list component

```typescript
type ListProps<T> = {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  keyExtractor: (item: T) => string;
  emptyState?: React.ReactNode;
};

function List<T>({ items, renderItem, keyExtractor, emptyState }: ListProps<T>) {
  if (items.length === 0) return <>{emptyState ?? null}</>;
  return (
    <ul>
      {items.map((item, index) => (
        <li key={keyExtractor(item)}>{renderItem(item, index)}</li>
      ))}
    </ul>
  );
}

// Usage — T is inferred from items:
<List
  items={users}
  keyExtractor={(u) => u.id}
  renderItem={(u) => <UserCard user={u} />}
/>
```

### Generic form field wrapper

```typescript
import { Control, FieldValues, Path } from "react-hook-form";

type FormFieldProps<T extends FieldValues> = {
  name: Path<T>;
  control: Control<T>;
  label: string;
};

function FormField<T extends FieldValues>({ name, control, label }: FormFieldProps<T>) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <Field invalid={!!fieldState.error} label={label} errorText={fieldState.error?.message}>
          <Input {...field} />
        </Field>
      )}
    />
  );
}
// name is typed to the keys of T — TypeScript errors if you pass an invalid field name
```

### Variance constraints

```typescript
// T must have an id property
function findById<T extends { id: string }>(items: T[], id: string): T | undefined {
  return items.find((item) => item.id === id);
}

// T must be an object (not primitive)
function cloneRecord<T extends object>(record: T): T {
  return { ...record };
}
```

---

## 3. Discriminated union props

### Variant components with exhaustive narrowing

```typescript
type AlertProps =
  | { variant: "success"; message: string }
  | { variant: "error"; message: string; onRetry?: () => void }
  | { variant: "loading" };

function Alert(props: AlertProps) {
  switch (props.variant) {
    case "success":
      return <div className="alert-success">{props.message}</div>;
    case "error":
      return (
        <div className="alert-error">
          {props.message}
          {props.onRetry && <button onClick={props.onRetry}>Retry</button>}
        </div>
      );
    case "loading":
      return <Spinner />;
    default:
      // Exhaustive check — TypeScript errors if a variant is unhandled
      const _exhaustive: never = props;
      return null;
  }
}
```

### Polymorphic `as` prop (render-as pattern)

```typescript
type TextProps<T extends React.ElementType = "p"> = {
  as?: T;
  children: React.ReactNode;
} & Omit<React.ComponentPropsWithoutRef<T>, "as" | "children">;

function Text<T extends React.ElementType = "p">({
  as,
  children,
  ...rest
}: TextProps<T>) {
  const Component = as ?? "p";
  return <Component {...rest}>{children}</Component>;
}

// Usage:
<Text as="h1" id="page-title">Hello</Text>
<Text as="span" className="label">Value</Text>
// TypeScript enforces props valid for the element type:
<Text as="a" href="/about">Link</Text>  // ✅ href is valid for <a>
<Text as="p" href="/about">Bad</Text>   // ❌ TypeScript error: href not valid for <p>
```

---

## 4. Type-safe context

### The null-sentinel + assertion hook pattern

```typescript
// auth-context.tsx
type User = { id: string; email: string; role: "admin" | "user" };

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  logout: () => void;
};

// null default — consumer will get a clear error rather than silent undefined behavior
const AuthContext = React.createContext<AuthContextValue | null>(null);

// This hook throws if used outside the provider, giving a clear error message
export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  
  const logout = React.useCallback(() => {
    setUser(null);
    // clear tokens, redirect, etc.
  }, []);
  
  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    logout,
  };
  
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

### Type-safe useReducer dispatch

```typescript
type Action =
  | { type: "INCREMENT"; by?: number }
  | { type: "DECREMENT" }
  | { type: "RESET"; to: number };

type State = { count: number };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "INCREMENT":
      return { count: state.count + (action.by ?? 1) };
    case "DECREMENT":
      return { count: state.count - 1 };
    case "RESET":
      return { count: action.to };  // TypeScript knows `to` exists on this branch
  }
}

const [state, dispatch] = React.useReducer(reducer, { count: 0 });
dispatch({ type: "INCREMENT", by: 5 });  // ✅
dispatch({ type: "RESET" });             // ❌ TypeScript: missing `to`
```

---

## 5. Type-safe API layer

### Infer types from zod schemas

```typescript
import { z } from "zod";

// Define schema once — use for both form validation and API response parsing
export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  firstName: z.string(),
  lastName: z.string(),
  role: z.enum(["admin", "user", "moderator"]),
  createdAt: z.string().datetime(),
});

// Infer the TypeScript type from the schema — single source of truth
export type User = z.infer<typeof UserSchema>;

// Parse API response at the boundary — validates at runtime
async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}/`);
  const data = await res.json();
  return UserSchema.parse(data);  // throws ZodError if response doesn't match schema
}

// Use the same schema in react-hook-form
const form = useForm<User>({
  resolver: zodResolver(UserSchema),
});
```

### The `satisfies` operator for API response shapes

```typescript
// satisfies: type-checks without widening to the type
// Useful for config objects and API clients

const API_ENDPOINTS = {
  users: "/api/users/",
  userDetail: (id: string) => `/api/users/${id}/`,
  posts: "/api/posts/",
} satisfies Record<string, string | ((id: string) => string)>;
// TypeScript knows API_ENDPOINTS.userDetail is specifically a function, not string | function
const url = API_ENDPOINTS.userDetail("123");  // typed as string, not string | function

// Without satisfies, we'd either lose the literal types or need a cast
```

### Shared schema pattern with DRF

```typescript
// api/schemas.ts — define once, use in both form and API
export const CreateProjectSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().optional(),
  isPublic: z.boolean().default(false),
});
export type CreateProjectInput = z.infer<typeof CreateProjectSchema>;

// In form:
const form = useForm<CreateProjectInput>({ resolver: zodResolver(CreateProjectSchema) });

// In mutation:
useMutation({
  mutationFn: (data: CreateProjectInput) => apiClient.post("/api/projects/", data),
});
```

---

## 6. Ref typing

### Basic typed ref

```typescript
// null initial value — the ref is null until the component mounts
const inputRef = React.useRef<HTMLInputElement>(null);

// Accessing the ref — TypeScript knows it may be null before mount
function focusInput() {
  inputRef.current?.focus();  // optional chaining for null safety
}

return <input ref={inputRef} />;
```

### forwardRef (React 18 and earlier)

```typescript
type InputProps = React.ComponentPropsWithoutRef<"input"> & {
  label: string;
};

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, ...rest }, ref) => (
    <label>
      {label}
      <input ref={ref} {...rest} />
    </label>
  )
);
Input.displayName = "Input";
```

### React 19 ref-as-prop pattern

In React 19, `forwardRef` is no longer needed — pass `ref` as a regular prop:

```typescript
type InputProps = React.ComponentPropsWithoutRef<"input"> & {
  label: string;
  ref?: React.Ref<HTMLInputElement>;  // optional ref prop
};

function Input({ label, ref, ...rest }: InputProps) {
  return (
    <label>
      {label}
      <input ref={ref} {...rest} />
    </label>
  );
}
// Usage is unchanged: <Input ref={myRef} label="Email" />
```

### useImperativeHandle

```typescript
type ModalRef = {
  open: () => void;
  close: () => void;
};

type ModalProps = { children: React.ReactNode };

const Modal = React.forwardRef<ModalRef, ModalProps>(({ children }, ref) => {
  const [isOpen, setIsOpen] = React.useState(false);
  
  React.useImperativeHandle(ref, () => ({
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
  }));
  
  return isOpen ? <div role="dialog">{children}</div> : null;
});

// Usage:
const modalRef = React.useRef<ModalRef>(null);
modalRef.current?.open();
```

---

## 7. Event handler typing

```typescript
// Input change
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  setValue(e.target.value);
};

// Select change
const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
  setSelected(e.target.value);
};

// Button click
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
  e.preventDefault();
};

// Form submit
const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
  e.preventDefault();
  // ...
};

// Keyboard
const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
  if (e.key === "Enter") doSomething();
};

// Synthetic event base type (when you don't need element-specific properties)
const handleFocus = (e: React.FocusEvent) => { ... };

// Inline handlers — inferred automatically from JSX context
<button onClick={(e) => console.log(e.currentTarget)} />
// e is inferred as React.MouseEvent<HTMLButtonElement>
```

---

## 8. Utility types in React context

```typescript
type UserFormValues = {
  firstName: string;
  lastName: string;
  email: string;
  role: "admin" | "user";
  bio?: string;
};

// Partial — all fields optional (useful for update endpoints)
type UpdateUserPayload = Partial<UserFormValues>;

// Required — remove optionals (useful for confirmed complete records)
type CompleteUser = Required<UserFormValues>;

// Pick — select subset of fields (form for one step of multi-step form)
type PersonalInfoValues = Pick<UserFormValues, "firstName" | "lastName" | "bio">;

// Omit — exclude fields (form without role assignment)
type SelfEditValues = Omit<UserFormValues, "role">;

// Readonly — freeze after creation (API response objects shouldn't be mutated)
type UserRecord = Readonly<UserFormValues & { id: string; createdAt: string }>;

// Parameters — extract arg types from a function
type FetchUserArgs = Parameters<typeof fetchUser>;  // [id: string]

// ReturnType — extract return type
type FetchUserResult = Awaited<ReturnType<typeof fetchUser>>;  // User
```

---

## 9. Module augmentation

### Extending Chakra UI's theme type

When adding custom tokens to Chakra's system:

```typescript
// theme.d.ts
import "@chakra-ui/react";

declare module "@chakra-ui/react" {
  interface ChakraThemeOverrides {
    colors: {
      brand: {
        50: string;
        100: string;
        // ... etc.
      };
    };
  }
}
```

This makes `colorScheme="brand"` and `color="brand.500"` type-check correctly.

### Extending global Window for third-party scripts

```typescript
// global.d.ts — no import/export needed (ambient declaration)
declare global {
  interface Window {
    analytics: {
      track: (event: string, properties?: Record<string, unknown>) => void;
      identify: (userId: string, traits?: Record<string, unknown>) => void;
    };
  }
}
```

### Extending React's type for experimental APIs

```typescript
// Useful during React 19 adoption when types lag implementation
declare module "react" {
  interface CSSProperties {
    [variable: `--${string}`]: string | number;  // allow CSS custom properties
  }
}
```

---

## Quick reference: common mistakes

| Pattern | Mistake | Fix |
|---|---|---|
| Children prop | `React.FC` implicit children | Add `children?: React.ReactNode` explicitly |
| Native element wrap | Lose all native props | Extend `ComponentPropsWithoutRef<"button">` |
| Context default | `createContext({})` — silently wrong | `createContext<T \| null>(null)` + assertion |
| API response type | `any` or unsupported cast | `z.infer` + `Schema.parse()` at boundary |
| Event handlers | Inline `any` | `React.ChangeEvent<HTMLInputElement>` etc. |
| ref before mount | Unchecked `.current.focus()` | `inputRef.current?.focus()` |
| forwardRef (React 18) | Missing generic | `forwardRef<HTMLDivElement, Props>()` |
