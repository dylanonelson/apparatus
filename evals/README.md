# Evals

**Node.js, [promptfoo](https://www.promptfoo.dev/)**

Automated evaluations for the `reader_api` LLM endpoints. The suite validates answer quality and edge-case behavior by running test cases against `/ask-automatic` and `/ask` with different prompt versions.

Node version is managed by nvm (see `.nvmrc` in repo root).

## Setup

```bash
cd evals
nvm use
npm install
cp .env.example .env    # fill in values
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `READER_API_URL` | Base URL of reader_api (e.g., `http://localhost:8000/api`) |
| `AUTH0_TOKEN` | JWT token for authenticated endpoints (`/ask-automatic`) |
| `OLLAMA_MODEL` | Local Ollama model name for judging passage-finder evals |
| `GEMINI_MODEL` | Google Gemini model for judging automatic-answers evals |
| `GOOGLE_API_KEY` | API key for Gemini |

The passage-finder evals use a local Ollama model as judge. The automatic-answers evals use Google Gemini. Both require the corresponding model to be available.

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

The `run-eval.sh` script expands to: `promptfoo eval --config features/{feature}/promptfooconfig.{config}.yaml --env-path .env [flags]`.

### Smoke test

Before running a full suite, validate the config and run a single case:

```bash
npx promptfoo validate --config features/automatic-answers/promptfooconfig.no-answer.yaml --env-path .env
./scripts/run-eval.sh automatic-answers no-answer --filter-first-n 1
npm run eval:view
```

## Test features

### Automatic answers (`features/automatic-answers/`)

Tests the `/ask-automatic` endpoint, which takes a reading location and viewport snapshot and automatically generates an explanation. The provider config (`providers.yaml`) runs each test case against prompt versions v0, v1, and v2 simultaneously.

**No-answer detection** (`test-cases/no-answer/`): verifies the model returns `IMPLIED_QUESTION_IS_UNCLEAR` when given meaningless selections. Assertion: exact string match (deterministic, no LLM judge).

- `insignificant-word-noun.yaml` - Single noun selection ("quarter")
- `insignificant-word-random.yaml` - Single word selection ("very")
- `sentence-fragment.yaml` - Partial sentence
- `long-passage-random.yaml` - Long passage with no clear question
- `long-passage-memorable.yaml` - Memorable passage requiring external context

**Missing-context quality** (`test-cases/missing-context/`): LLM-graded rubrics checking tone (scholarly, objective, non-editorializing) and factuality against reference answers. Assertions: `llm-rubric` (threshold 3/5) + `factuality` (via Gemini).

- `black-prince.yaml` - Historical allusion
- `castors-sixes-sevens.yaml` - Victorian household terminology
- `markleham-marplot.yaml` - Literary reference (Susanna Centlivre)
- `mr-bodgers.yaml` - Deceased parishioner memorial
- `murdstone-lark.yaml` - Idiomatic expression
- `prophetic-pins.yaml` - Victorian-era custom
- `spenlow-punch.yaml` - Puppet theater reference (Punch and Judy)

### Passage finder (`features/passage-finder/`)

Tests the freeform `/ask` endpoint for "catch me up" and "find passage" queries against Anna Karenina. Assertion: `llm-rubric` scored by local Ollama model.

- Test cases in `anna-karenina.yaml`

## Adding a test case

### No-answer case

Create a YAML file in `features/automatic-answers/test-cases/no-answer/`:

```yaml
- description: "Brief description of what this tests"
  vars:
    request_body:
      publication_id: "david-copperfield_std-ebks-2025"
      locator:
        href: "epub/text/chapter-XX.xhtml"
        type: "application/xhtml+xml"
        locations:
          progression: 0.5
          totalProgression: 0.1
          position: 42
      viewport:
        positions: [42]
        text: "Full visible text on screen..."
        selection_text: "The selected portion"
    expected_answer: IMPLIED_QUESTION_IS_UNCLEAR
```

### Missing-context case

Same structure but in `test-cases/missing-context/`, adding a `reference_answer` field:

```yaml
- description: "Brief description"
  vars:
    request_body:
      # ... same as above
    reference_answer: "Expected gold-standard explanation..."
```

## Directory structure

```
evals/
├── promptfooconfig.yaml                   # Main config for passage-finder evals
├── ak-rubric.yaml                         # Rubric prompt template for Anna Karenina
├── rubric.txt                             # Scoring criteria (1-5 scale, 3 criteria)
├── scripts/
│   └── run-eval.sh                        # Runner for feature-specific configs
├── features/
│   ├── automatic-answers/
│   │   ├── promptfooconfig.no-answer.yaml       # Config for no-answer tests
│   │   ├── promptfooconfig.missing-context.yaml # Config for missing-context tests
│   │   ├── providers.yaml                       # HTTP provider config (v0, v1, v2)
│   │   ├── rubric-prompt.yaml                   # Tone/quality grading rubric
│   │   └── test-cases/
│   │       ├── no-answer/                       # 5 deterministic test cases
│   │       ├── missing-context/                 # 7 LLM-graded test cases
│   │       └── textual-reference/               # (in progress)
│   └── passage-finder/
│       └── anna-karenina.yaml                   # Passage-finder test cases
├── .env.example                           # Environment variable template
├── .nvmrc                                 # Node version
└── package.json                           # Scripts and promptfoo dependency
```
