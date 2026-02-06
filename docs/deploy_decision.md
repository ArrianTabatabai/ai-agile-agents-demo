# Deploy / Preview Decision

Chosen approach: Render.

Reason:
- Simple hosting for Python apps.
- Produces a stable URL for Product Owner validation after CI success.

Definition of preview success:
- URL loads.
- Basic endpoint responds (e.g., /health).
- A user-facing change is visible when implemented.