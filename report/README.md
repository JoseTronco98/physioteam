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
python report/check.py <preview_dir>   # prints the report to a letter PDF, counts pages, screenshots slides
```

- `report.src.html`, `slides.src.html`: the text, with `⟦MARKERS⟧` for every measured value.
- `data/user_test.json` (optional): the therapist's test results. Copy `data/user_test.template.json`,
  fill it in, and re-run `fill.py` + `build.py`: the user-test section, the quote and the time model
  (her own minutes per task) update automatically. Protocol: `user_test_guide.md`.
- Model outputs vary between runs: re-running gives the same order of magnitude, not identical decimals.
