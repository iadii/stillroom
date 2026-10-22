# Contributing

Thanks for helping improve Stillroom. Please open an issue describing the user problem before making large changes. Small fixes and documentation improvements can go straight to a pull request.

1. Fork the repository and create a focused branch.
2. Set up the project using the README. Keep API keys in `.env`; never commit keys, runtime `data/`, or personal documents.
3. Run `uv run pytest -q` in `backend/`, and `npm run format:check && npm run build` in `frontend/`.
4. Include a short explanation of behavior changes and any remaining limits in your pull request.

For model behavior changes, add a test with a concrete source document and expected verification outcome. Do not use real private documents in fixtures. Preserve the human approval gate and the ability to undo archive moves.
