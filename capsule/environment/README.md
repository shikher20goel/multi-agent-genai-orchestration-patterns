# capsule/environment — pointer

The capsule's environment is defined at the repository root:

- Pinned dependency closure: `../../environment/requirements.lock`
- Container recipe: `../../Dockerfile` (python:3.11-slim, digest-pin
  comment slot, non-root user)

Either reproduces the environment the published results were made
with; see `../../environment/README.md`.
