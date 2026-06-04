# environment/

`requirements.lock` pins the exact dependency closure (runtime + dev)
the published results were produced with, generated from
`python3 -m pip freeze` filtered to the project's dependency closure.

Reproduce the environment with either:

```bash
python3 -m pip install -r environment/requirements.lock
python3 -m pip install -e . --no-deps
```

or the pinned `Dockerfile` at the repository root
(`docker build -t agentorch .`).
