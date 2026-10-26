# Report and slides: how they are built

Everything in `report.html` and `slides.html` comes from measured data and can be rebuilt:

```
# 1. measurements (live model, needs PORTKEY_API_KEY)
python -m tools.report_data report/data/report_data.json      # ~$0.07, ~7 min: 51 story steps, autopilot week, traces
python -m tools.eval_quality report/data/eval_quality.json    # ~$0.06, ~6 min: Clinical Scribe on 30 notes

# 2. screenshots (needs a local server without an access code on port 8001)
#    PowerShell: $env:ACCESS_CODE=" "; python -m uvicorn backend.main:app --port 8001
python -m tools.shots report/shots

# 3. documents
python report/fill.py      # fills the numbers, tables and charts into *.ready.html
python report/build.py     # embeds the screenshots -> report/out/*.html (+ copy to ../deliverable/)
python report/check.py [preview_dir]   # (default report/preview) prints the report to a letter PDF, counts pages, screenshots slides
```

- `report.src.html`, `slides.src.html`: the text, with `⟦MARKERS⟧` for every measured value.
- `data/user_test.json`: the recorded session with a practicing physical therapist (her pains, her time
  estimate of about 2 hours a day, her quotes, and her ~2 minutes per booking message). It fills Exhibit 18a,
  the quotes and the time model; without it the report shows a "to be completed" box. Template:
  `data/user_test.template.json`; protocol for a longer timed test: `user_test_guide.md`.
- Model outputs vary between runs: re-running gives the same order of magnitude, not identical decimals.
