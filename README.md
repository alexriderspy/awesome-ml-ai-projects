# awesome-ml-ai-projects

Hands-on ML and AI projects you build yourself. Each one has working reference code, a practice eval that scores your version out of 100, offline tests and a real demo.

## Projects

### LLM apps

| Project | What you build | Level | Video |
|---|---|---|---|
| [YouTube Summarizer](projects/llm-apps/youtube-summarizer) | Timestamped summaries of any video | Beginner | [watch](https://www.youtube.com/watch?v=xDQL3vWwcp0) |
| [PPT Generator Agent](projects/llm-apps/ppt-generator-agent) | A topic in, a real .pptx deck out | Beginner | [watch](https://www.youtube.com/watch?v=xgSGGFDzu98) |
| [Chat with PDF](projects/llm-apps/chat-with-pdf) | Answers that cite page numbers | Beginner | |
| [Structured Extraction](projects/llm-apps/structured-extraction) | Messy text to validated JSON | Beginner | |

### Agents

| Project | What you build | Level | Video |
|---|---|---|---|
| [Tool Calling Basics](projects/agents/tool-calling-basics) | The tool-calling loop from scratch | Beginner | [watch](https://www.youtube.com/watch?v=XtjEE5E-GTw) |
| [Multi-Agent Blog Writer](projects/agents/multi-agent-blog-writer) | Five agents that research and write with citations | Intermediate | [watch](https://www.youtube.com/watch?v=KiMF4QJ-HOE) |
| [GitHub Issue Triage Agent](projects/agents/github-issue-triage-agent) | Labels, duplicate detection, reply drafts | Intermediate | |
| [Coding Agent that Fixes Failing Tests](projects/agents/coding-agent-fixes-tests) | An agent that edits code until pytest passes | Intermediate | |
| [Web Scraping Agent](projects/agents/web-scraping-agent) | Describe the data, get JSON records | Intermediate | |
| [Investment Research Agent](projects/agents/investment-research-agent) | Stock comparison reports with checked numbers | Intermediate | |
| [Recruitment Agent Team](projects/agents/recruitment-agent-team) | Screening, interview questions, scheduling | Intermediate | |
| [Tic-Tac-Toe LLM Battle](projects/agents/tic-tac-toe-llm-battle) | LLMs vs a perfect minimax player | Beginner | |
| [Hacker News Briefing](projects/agents/hacker-news-briefing) | A daily brief ranked by your interests | Intermediate | |
| [Dependency Doctor](projects/agents/dependency-doctor) | Finds problems in requirements files | Beginner | |

### Classic ML

| Project | What you build | Level | Video |
|---|---|---|---|
| [Linear Regression from Scratch](projects/classic-ml/linear-regression-from-scratch) | Closed form and gradient descent in NumPy | Beginner | [watch](https://www.youtube.com/watch?v=Ho7WQBMQ038) |
| [Titanic](projects/classic-ml/titanic-kaggle) | Your first Kaggle-style project | Beginner | [watch](https://www.youtube.com/watch?v=UPC8q_IUiLQ) |
| [House Price App](projects/classic-ml/house-price-app) | A deployed model with an uncertainty band | Beginner | [watch](https://www.youtube.com/watch?v=1ZhBWDdRn6o) |
| [Weather Prediction App](projects/classic-ml/weather-prediction-app) | Tomorrow's temperature vs a persistence baseline | Beginner | [watch](https://www.youtube.com/watch?v=DmCAFi896IU) |

### Fine-tuning

These include the code and a Colab notebook for each run. Training needs a GPU for the full-size models.

| Project | What you build | Level | Video |
|---|---|---|---|
| [Fine-tune Llama 3.2 3B](projects/fine-tuning/finetune-llama-3.2-3b) | LoRA SFT on FineTome-100k with Unsloth | Intermediate | [watch](https://www.youtube.com/watch?v=dn2anUU0d0U) |
| [Fine-tune on Your Own Data](projects/fine-tuning/finetune-on-your-own-data) | Clean your notes and chats into a dataset, then train | Intermediate | [watch](https://www.youtube.com/watch?v=OxfeK423y2I) |
| [Qwen2-VL LaTeX OCR](projects/fine-tuning/finetune-qwen2-vl-latex-ocr) | Formula image to LaTeX with a vision-language model | Advanced | [watch](https://www.youtube.com/watch?v=i5kDh35sJ9M) |
| [Small Model Beats Big](projects/fine-tuning/small-model-beats-big) | A 360M model vs a big API model on ticket routing | Intermediate | |

## How each project works

```
projects/<category>/<project>/
  README.md        milestones, run commands, how it's scored, leaderboard
  src/             reference implementation
  app.py           Streamlit UI (most projects)
  eval/            original practice set + run_eval.py → OVERALL <n>/100
  tests/           offline tests, no API key needed
  demo/            real outputs and screenshots
```

Build it yourself following the milestones, or read the reference code. Then run the eval and add your score to the project's leaderboard.

## Models

LLM projects work with any OpenAI-compatible endpoint. They default to a local model through [Ollama](https://ollama.com), so you don't need an API key:

```bash
ollama pull llama3.2
cp .env.example .env && export $(xargs < .env)
```

To use a hosted model, set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`. The reference scores were run with `deepseek-flash`.

## Contributing

Post your score, add a project, or fix a bug: see [CONTRIBUTING.md](CONTRIBUTING.md) and [CONVENTIONS.md](CONVENTIONS.md).

## License

MIT
