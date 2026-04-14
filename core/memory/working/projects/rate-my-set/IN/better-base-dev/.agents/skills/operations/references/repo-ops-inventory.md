# Repository Ops Inventory and Conventions

This inventory is based on reading the current `backend/**/ops.py` and
`backend/**/ops/**/*.py` modules.

## Inventory (Non-test Ops Modules)

- `backend/accounts/ops/accounts.py`
- `backend/accounts/ops/data_consistency.py`
- `backend/accounts/ops/invitations.py`
- `backend/accounts/ops/memberships.py`
- `backend/accounts/ops/uploaded_images.py`
- `backend/accounts/ops/users.py`
- `backend/accounts/ops/users_app_states.py`
- `backend/auth/ops/change_email.py`
- `backend/auth/ops/change_password.py`
- `backend/auth/ops/login.py`
- `backend/auth/ops/logout.py`
- `backend/auth/ops/password_validators.py`
- `backend/auth/ops/reset_password.py`
- `backend/auth/ops/signup.py`
- `backend/auth/ops/verify_email.py`
- `backend/base/ops/debugging.py`
- `backend/base/ops/emails.py`
- `backend/base/ops/enabled_features.py`
- `backend/base/ops/environment.py`
- `backend/base/ops/exceptions.py`
- `backend/base/ops/frontend_extra_signaling.py`
- `backend/base/ops/security.py`
- `backend/base/ops/wrapped_secret_values.py`

## Existing Patterns To Mirror

- Action-oriented public entrypoints (`create_*`, `update_*`, `delete_*`, `attempt_*`,
  `send_*`).
- Validation-first patterns (`validate_can_*` appears in accounts invitations/
  memberships ops).
- Explicit result types via dataclasses / named tuples for non-trivial workflows.
- Internal helper functions are underscored (`_helper_name`) and kept non-public.
- Transaction-sensitive flows are explicit in ops code.
- Ops modules are reusable across HTTP and non-HTTP entry points.

## Important Existing Examples

- `backend/accounts/ops/invitations.py`:
- Rich `validate_can_*` gatekeeping plus follow/accept/decline action operations.
- `backend/auth/ops/signup.py` and `backend/auth/ops/reset_password.py`:
- `attempt_*` operation pattern with explicit success/failure result contracts.
- `backend/accounts/ops/users.py`:
- Creation/update operations that coordinate model lifecycle and related records.

## Code Review Focus For Ops Paths

1. Business logic belongs in operations, not duplicated in views/tasks/commands.
2. Preconditions and permission/state checks are explicit.
3. Side effects and transactional boundaries are obvious.
4. Public API surface is clear and stable.
5. Tests cover both happy path and key failure cases.
