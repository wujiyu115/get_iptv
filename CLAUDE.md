# CLAUDE.md

## Testing rule (mandatory)

After changing code, you MUST add new tests or update existing ones to cover the
change, then run the full suite and confirm it is all green before considering
the work done. Do not claim completion on unverified code.

- Backend tests live in `backend/tests/` (pytest).
- Run from the `backend/` directory:

  ```bash
  cd backend && python -m pytest tests/ -q
  ```

- Every test must pass. If a test fails, fix the code or the test — never skip,
  xfail, or delete a test to make the suite green.
- New behavior → new test. Changed behavior → update the affected test.
