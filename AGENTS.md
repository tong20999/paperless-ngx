# Working on this Paperless-ngx fork

Read [CONTRIBUTING.md](CONTRIBUTING.md#use-of-ai-tools) before editing. `origin` is the fork and `upstream` is the official Paperless-ngx repository.

## Branches

- Keep `dev` at the same commit as `upstream/dev`. Use fast-forward updates for routine syncs.
- Start fork changes on `feature/<name>` from `develop`. Merge completed features into `develop`. The MCP integration lives on `feature/mcp`.
- Merge upstream updates into `develop` and resolve conflicts against current Paperless behavior. Cut `release/<version>` from tested `develop` commits for deployment. See the [sync and deployment commands](docs/development.md#updating-this-forks-mcp-integration).

## Changes and verification

- Read the affected code, tests, and docs. MCP tools use the existing REST views, serializers, authentication, and permissions. Keep credentials and private documents out of fixtures and logs.
- Add regression tests for changed behavior and update the relevant docs. Run `uv run --locked pytest src/paperless/tests/test_mcp.py` for MCP changes and the affected REST tests. For UI changes, run `pnpm test` and `pnpm lint` in `src-ui/`.
- Disclose AI-assisted changes and report the checks actually run. Leave PR creation, verification, and submission to a human. Discuss new features upstream first. Upstream excludes mostly or entirely AI-derived PRs.
- Issue reports describe observed behavior, reproduction steps, and logs. Follow [SECURITY.md](SECURITY.md) for human verification and private reporting of security issues.
