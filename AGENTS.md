# Agent Guidelines

## Development Workflow

### Running tests
```
pytest
```

### Linting
```
ruff check .
```

## Cleanup Before Completion

Before marking work complete (setting `canValidate: true` or equivalent), delete any
temporary debugging scripts you created during investigation. These must not be committed:

- `repro.py`, `repro_*.py`
- `reproduce_issue.py`, `reproduce_*.py`
- `real_repro.py`
- `debug_*.py`, `test_repro_*.py`
- Any one-off script in the repo root that is not part of the project

Proper test cases belong in `tests/`. Everything else gets deleted.

## Acceptance Criteria (Always Required)

Every task must satisfy this criterion before completion:

- **No debug scripts in repo root**: Files matching `repro*.py`, `reproduce*.py`,
  `real_repro*.py`, `debug_*.py` must not exist in the repository root. Verify with:
  ```
  ls repro*.py reproduce*.py real_repro*.py debug_*.py 2>/dev/null && echo FAIL || echo PASS
  ```
