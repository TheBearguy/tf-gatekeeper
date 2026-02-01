# Terraform Gatekeeper - Development Guide

This guide covers how to set up your development environment and contribute to tf-gate.

## Prerequisites

- Python 3.9+
- Terraform >= 1.0
- OPA (Open Policy Agent) binary
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/anomalyco/tf-gatekeeper.git
cd tf-gatekeeper
```

### 2. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
# Install in development mode with all dev dependencies
pip install -r requirements-dev.txt
pip install -e .
```

### 4. Install OPA

Download OPA binary from [openpolicyagent.org](https://www.openpolicyagent.org/docs/latest/#running-opa) and ensure it's in your PATH:

```bash
# Linux/Mac
curl -L -o opa https://openpolicyagent.org/downloads/v0.60.0/opa_linux_amd64_static
chmod 755 ./opa
sudo mv opa /usr/local/bin/

# Verify
opa version
```

### 5. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tf_gate --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### 6. Code Quality Checks

Before committing, ensure your code passes all quality checks:

```bash
# Format code with black
black src tests

# Lint with ruff
ruff check src tests

# Type check with mypy
mypy src/tf_gate

# Run all tests
pytest
```

Or use the pre-commit hook:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

## Project Structure

```
tf-gatekeeper/
├── src/
│   └── tf_gate/           # Main package
│       ├── __init__.py
│       ├── cli.py         # CLI entry point
│       ├── phases/        # 4-phase validation pipeline
│       │   ├── __init__.py
│       │   ├── phase1_ingest.py
│       │   ├── phase2_opa.py
│       │   ├── phase3_context.py
│       │   └── phase4_intent.py
│       └── utils/         # Utility modules
│           ├── __init__.py
│           ├── blast_radius.py
│           └── git.py
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── unit/
│   └── integration/
├── policies/              # Default Rego policies
│   ├── protected.rego
│   ├── security.rego
│   └── cost.rego
├── pyproject.toml         # Package configuration
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
└── README.md
```

## Development Workflow

### Making Changes

1. Create a new branch for your feature/fix
2. Write tests for your changes
3. Implement your changes
4. Run tests and ensure they pass
5. Run linting and type checking
6. Commit with a descriptive message
7. Push and create a PR

### Testing Guidelines

- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test interaction with Terraform and OPA
- Use pytest fixtures for common setup
- Mock external dependencies (Terraform CLI, OPA, LLMs)
- Aim for >80% code coverage

### Writing Tests

```python
# tests/unit/test_blast_radius.py
import pytest
from tf_gate.utils.blast_radius import calculate_blast_radius

def test_calculate_blast_radius_empty():
    """Test blast radius calculation with no changes."""
    result = calculate_blast_radius([])
    assert result.level == "green"
    assert result.score == 0
```

### Running Specific Tests

```bash
# Run specific test file
pytest tests/unit/test_blast_radius.py

# Run specific test function
pytest tests/unit/test_blast_radius.py::test_calculate_blast_radius_empty

# Run with verbose output
pytest -v

# Run with debugging
pytest --pdb
```

## Configuration

### Local Configuration

Create a local config file for testing:

```yaml
# tf-gate.yaml
opa:
  policy_dir: "./policies"
  strict_mode: false  # Don't fail on deny rules during testing

phases:
  phase_3_time_gating:
    friday_cutoff_hour: 15
    weekend_blocking: false  # Disable during development
  
  phase_4_intent:
    enabled: false  # Disable LLM checks during development

blast_radius:
  thresholds:
    green: 5
    yellow: 20
    red: 50
```

## Debugging

### Enable Debug Logging

```bash
tf-gate --verbose apply
# OR
tf-gate -v apply
```

### Use PDB

Insert `import ipdb; ipdb.set_trace()` in your code for interactive debugging.

## Common Issues

### OPA Not Found

Ensure OPA is installed and in your PATH:

```bash
which opa
opa version
```

### Import Errors

Make sure you've installed the package in editable mode:

```bash
pip install -e .
```

### Terraform Not Found

Ensure Terraform is installed:

```bash
terraform version
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Tag the release: `git tag -a v0.1.0 -m "Release v0.1.0"`
4. Push tags: `git push origin v0.1.0`
5. GitHub Actions will automatically build and publish to PyPI

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Ensure all checks pass
6. Submit a pull request

## Resources

- [Terraform Plan JSON Format](https://developer.hashicorp.com/terraform/internals/json-format)
- [OPA Documentation](https://www.openpolicyagent.org/docs/latest/)
- [Rego Policy Language](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Code Style](https://black.readthedocs.io/)
- [Ruff Linter](https://docs.astral.sh/ruff/)

## Questions?

Open an issue on GitHub or contact the maintainers.
