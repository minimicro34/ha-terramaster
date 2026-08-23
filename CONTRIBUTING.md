# Contributing to TerraMaster TOS for Home Assistant

Thank you for your interest in contributing to TerraMaster TOS for Home Assistant.

## Development setup

Clone the repository:

```bash
git clone https://github.com/minimicro34/ha-terramaster.git
cd ha-terramaster
```

Install the test dependencies:

```bash
pip install -r requirements_test.txt
```

## Validation

Before submitting a change, run:

```bash
ruff check .
mypy custom_components/terramaster
pytest
```

All checks must pass before submitting a pull request.

GitHub Actions also runs:

- Ruff
- mypy
- pytest
- Home Assistant Hassfest
- HACS validation

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
