# Evals

**Node.js, [promptfoo](https://www.promptfoo.dev/)**

Automated evaluations for the `reader_api` LLM endpoints. The suite validates answer quality and edge-case behavior by running test cases against `/ask-automatic` and `/ask` with different prompt versions.

Node version is managed by nvm (see `.nvmrc`).

## Setup

```bash
cd evals
nvm use
npm install
cp ENV_EXAMPLE .env    # fill in values
```

See `ENV_EXAMPLE` for the full list of environment variables and descriptions. The passage-finder evals use a local Ollama model as judge; the automatic-answers evals use Google Gemini.

## Running evaluations

Evals are organized by feature. Each feature has its own promptfoo config file.

```bash
# Passage finder (Anna Karenina, uses Ollama judge)
npm run eval

# Automatic answers - no-answer cases (deterministic, no judge needed)
./scripts/run-eval.sh automatic-answers no-answer

# Automatic answers - missing-context cases (uses Gemini judge)
./scripts/run-eval.sh automatic-answers missing-context

# Pass additional promptfoo flags after the feature/config args
./scripts/run-eval.sh automatic-answers no-answer --filter-first-n 1

# View results in browser
npm run eval:view

# Hot reload during development
npm run eval:watch
```

### Smoke test

Before running a full suite, validate the config and run a single case:

```bash
npx promptfoo validate --config features/automatic-answers/promptfooconfig.no-answer.yaml --env-path .env
./scripts/run-eval.sh automatic-answers no-answer --filter-first-n 1
npm run eval:view
```
