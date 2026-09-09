# Permissions

CollabTrace separates account identity, authorization and contribution attribution.

## Three independent concepts

1. **System Role** — `User.role`. `ADMIN` manages System Users and diagnostics; `MEMBER` is a Standard User.
2. **Repository Role** — `RepositoryAccess.role`. It controls writes for one repository only.
3. **Member Mapping** — links a CollabTrace user to a GitHub contributor for attribution. It grants no access.

Example: Alice may be a Standard User, Repo A ADMIN, Repo B MEMBER, and mapped to `@alice-dev`. None of those facts implies another.

## Permission matrix

| Function | Repo ADMIN | Repo MEMBER | System ADMIN |
|---|---:|---:|---:|
| View repository Dashboard/RCI/Evidence | Yes | Yes | Yes, as normal read access |
| Analyze a brand-new repository | Yes | Yes | Yes |
| Become ADMIN of that newly created repository | Yes | Yes | Yes |
| Re-analyze/refresh an existing repository | Yes | No | Only if also Repo ADMIN |
| Manual Sync | Yes | No | Only if also Repo ADMIN |
| Member Mapping | Yes | No | Only if also Repo ADMIN |
| Repository Access management | Yes | No | Only if also Repo ADMIN |
| Repository Admin Center | Yes | No | Only if also Repo ADMIN |
| System Users | No, unless System ADMIN | No, unless System ADMIN | Yes |

All authenticated users can read listed repositories in V1; no explicit access row means the effective repository role is `MEMBER`.

## Important invariants

- System Admin is not automatically Repository Admin.
- Repository Admin cannot manage System Users unless also System Admin.
- The last explicit Repository Admin cannot be demoted.
- An existing Repository MEMBER cannot gain ADMIN by submitting Analyze again; no unauthorized sync runs.
- Switching repositories recalculates visible controls from that repository's role.
- Mapping a user to a contributor never changes either role.

## Bootstrap and recovery

`python -m app.cli create-admin` creates a System Admin interactively. On startup, legacy repositories without any administrator are assigned to the earliest active System Admin. `python -m app.cli grant-repository-admin` is an explicit interactive recovery command.
