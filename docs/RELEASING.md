# Releasing prism-ai-lint

How a release is cut and published, the one-time setup it needs, and how to recover a failed publish.
Rationale: [DECISIONS.md](../DECISIONS.md) D-012 (computed version) and D-039 (Trusted Publishing, Docker Hub).

## How a release happens

Every push to `main` runs `.github/workflows/release.yml`:

1. `release`: git-cliff computes the next version from the Conventional Commits since the last tag. When it
   advances, the job tags `vX.Y.Z` and creates the GitHub release with generated notes. No version is edited by hand.
2. `build`: builds the sdist and wheel once (artifact `dist`).
3. `publish-testpypi` (environment `testpypi`), then `publish-pypi` (environment `pypi`): upload `dist` through
   Trusted Publishing (OIDC, `id-token: write`). No API token is stored.
4. `docker`: builds `docker.io/chrys4/prism-ai-lint:<version>` and `:latest` from that wheel and pushes them.

Each step needs the previous one: a TestPyPI failure skips PyPI and Docker Hub.

## One-time setup

### PyPI and TestPyPI: pending publishers

The project does not exist on either index until its first upload, so each index needs a *pending publisher*.
These are two separate accounts. Sign in, then open:

- PyPI: <https://pypi.org/manage/account/publishing/>
- TestPyPI: <https://test.pypi.org/manage/account/publishing/>

Under "GitHub", fill in:

| Field | PyPI | TestPyPI |
|---|---|---|
| PyPI Project Name | `prism-ai-lint` | `prism-ai-lint` |
| Owner | `chrysa` | `chrysa` |
| Repository name | `prism-ai-lint` | `prism-ai-lint` |
| Workflow name | `release.yml` | `release.yml` |
| Environment name | `pypi` | `testpypi` |

The environment name must match the job's `environment.name` exactly. A pending publisher does not reserve the
name: the first successful upload creates the project and turns it into a normal publisher.

### GitHub repository settings

- Environments `pypi` and `testpypi` exist, restricted to the `main` branch.
- Variable `DOCKERHUB_USERNAME`: the Docker Hub account that owns the image (`chrys4`).
- Secret `DOCKERHUB_TOKEN`: a Docker Hub access token with read/write scope on `chrys4/prism-ai-lint`.
- The secret `PYPI_API_TOKEN` is no longer read by any workflow (D-039 supersedes D-020/D-028); delete it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Trusted publishing exchange failure` … `invalid-publisher` | No publisher matches the repository, workflow and environment claims | Add or correct the pending publisher above |
| `docker` fails at login | `DOCKERHUB_TOKEN` missing or expired | Create the token on Docker Hub and set the secret |
| No release, "nothing to release" | No `feat`/`fix`/breaking commit since the last tag | Expected; merge a release-worthy commit |

## Recovering a failed publish

The tag and the GitHub release already exist when a publish job fails, so do not retag. Once the setup is fixed,
rerun only the failed jobs of the last release run (the `dist` artifact is reused):

```sh
gh run list --workflow release.yml --branch main --limit 1
gh run rerun <run-id> --failed
```

Older tags that were never published can stay unpublished; the next release publishes the current version.
