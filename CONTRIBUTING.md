# Contributing to TerraMaster TOS for Home Assistant

Thank you for your interest in contributing to TerraMaster TOS for Home Assistant.

## Development setup

Clone the repository:

```bash
git clone https://github.com/minimicro34/ha-terramaster.git
cd ha-terramaster
```

Create an isolated Python environment and install the test dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements_test.txt
```

Use Python 3.14, matching the CI workflow. Node.js 22 is needed for the bundled Lovelace card tests.

## Validation

Before submitting a change, run:

```bash
ruff check .
mypy custom_components/terramaster
pytest --cov=custom_components.terramaster --cov-report=term-missing --cov-report=xml --cov-fail-under=80
node --check custom_components/terramaster/www/terramaster-card.js
node --test tests/js/*.test.cjs
```

All checks must pass before submitting a pull request. Python coverage must remain at or above **80%**. The generated `coverage.xml` report is local and is not committed.

GitHub Actions also runs:

- Ruff
- mypy
- pytest with a minimum 80% Python coverage threshold
- JavaScript syntax and Node.js card tests
- Home Assistant Hassfest
- HACS validation

## Translations

When adding or changing user-facing strings:

- update `custom_components/terramaster/strings.json`;
- update the corresponding files in `custom_components/terramaster/translations/`;
- keep translation keys synchronized between languages;
- do not remove existing translation keys without checking their usage.

Run the validation checks before committing translation changes.

## Pull requests

Please:

- keep changes focused and reasonably small;
- describe what the change does and why;
- include tests for new behavior or bug fixes when appropriate;
- update documentation when behavior or configuration changes;
- avoid unrelated formatting or refactoring.

For significant changes, please open an issue before submitting a pull request.

## Security

Do not report security vulnerabilities in public issues.

Please follow the instructions in [SECURITY.md](SECURITY.md).

## License

By contributing to this project, you agree that your contributions will be licensed under the [GNU General Public License v3.0 or later](LICENSE).
