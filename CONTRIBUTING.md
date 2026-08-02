# Contributing to ModuMesh MakerLab

We welcome contributions! Here's how to get started.

## Development Workflow

1. **Fork and clone** the repository.
2. **Create a feature branch** from `main`: `git checkout -b feat/your-feature`.
3. **Make your changes** with small, focused commits.
4. **Run the CI suite locally** where practical (`make test`, `make smoke`, `npx prettier --check .`) before pushing.
5. **Open a pull request** against `main`. Use the PR template. GitHub Actions CI must pass.

## Pull Request Guidelines

- One feature or fix per PR — no scope creep.
- Include tests for new code.
- Update documentation (README, ADRs, API docs) where relevant.
- Add migration notes for schema or config changes.
- Add rollback notes for operations that affect running instances.
- No CI failures — failing PRs will not be reviewed.

## Code Style

- TypeScript: strict mode, Prettier for formatting.
- Python: type-annotated, `black`-compatible style.
- Commit messages: conventional commits preferred (`feat:`, `fix:`, `docs:`, etc.).

## Code of Conduct

This project follows a [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful and constructive.

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for our disclosure process.
