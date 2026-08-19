"""Build the customized Teams-feature HTML report from recorded run results.

``tests/test_teams_feature.py`` appends one JSON row per scenario to
``reports/teams_results.jsonl`` via its ``_record_result`` helper. That file is
raw data; this module turns the *latest* run's rows into the readable
``reports/teams_feature_report.html`` breakdown (stat tiles, a failed-tests
callout, and a pass/fail table per feature).

"Latest run" is resolved by keeping the last recorded row per scenario name:
each run writes every scenario exactly once, so the last occurrence of each name
is always that scenario's most recent outcome. This is why re-running only the
timed-out scenarios still updates the report correctly.

Run standalone::

    python -m utils.generate_teams_report

or let ``tests/conftest.py`` call :func:`generate_report` after every test run.
"""

import html
import json
import os
from datetime import datetime

from utils.common import CommonUtils

RESULTS_FILE = os.path.join("reports", "teams_results.jsonl")
ALL_RESULTS_FILE = os.path.join("reports", "all_results.jsonl")
REPORT_FILE = os.path.join("reports", "teams_feature_report.html")
DATA_FILE = os.path.join("data", "teams_feature_data.json")
ENVIRONMENT = "qgpt-staging"

# Recorded statuses that count as a failing Teams scenario (everything else passes).
FAIL_STATUSES = {"NO_RESPONSE", "NO_KEYWORD", "EMPTY", "FAIL_MARKER"}

# Generic per-test statuses recorded by the conftest hook for ALL 55 tests.
GENERIC_FAIL = {"FAIL", "ERROR"}

# Order the suite groups appear in the report; extras append after.
GROUP_ORDER = ["Login", "Agent Query", "Teams Feature", "Teams Message"]


def _load_latest_rows():
    """Return {scenario_name: row} for the most recent run.

    Keeping the last row seen per name collapses the append-only history down to
    the latest outcome for each scenario.
    """
    latest = {}
    if not os.path.exists(RESULTS_FILE):
        return latest
    with open(RESULTS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = row.get("name")
            if name:
                latest[name] = row
    return latest


def _clean(text, limit=200):
    """Collapse whitespace and trim an agent reply down to a table-friendly snippet."""
    snippet = " ".join((text or "").split())
    if len(snippet) > limit:
        snippet = snippet[:limit].rstrip() + "…"
    return snippet


def _result_text(row):
    """Human-readable 'Result' cell for one scenario row."""
    status = row.get("status", "")
    detail = row.get("detail", "")
    response = _clean(row.get("response", ""))
    if status == "PASS":
        return html.escape(response) if response else "Passed."
    if status == "NO_RESPONSE":
        return "No agent reply before the timeout."
    if status == "EMPTY":
        return "Agent returned an empty response."
    if status == "NO_KEYWORD":
        got = f" Got: {html.escape(response)}" if response else ""
        return "Reply did not contain any expected keyword." + got
    if status == "FAIL_MARKER":
        got = f" Got: {html.escape(response)}" if response else ""
        return f"Reply tripped a failure marker ({html.escape(detail)})." + got
    return html.escape(detail or status)


def _fail_reason(row):
    """A readable 'why it failed' sentence for the Failed Tests callout.

    Turns the terse recorded status/detail into an explanation, and quotes what
    the agent actually replied so the reader has context without opening the
    raw data.
    """
    status = row.get("status", "") or ""
    detail = row.get("detail", "") or ""
    response = _clean(row.get("response", ""), limit=240)

    if status == "NO_RESPONSE":
        return "No agent reply before the timeout — the request exceeded the response window."
    if status == "EMPTY":
        return "The agent returned an empty response."
    if status == "NO_KEYWORD":
        base = "Reply contained none of the expected keywords."
        return f"{base} Agent said: “{response}”" if response else base
    if status == "FAIL_MARKER":
        marker = detail.replace("marker:", "").strip()
        base = (
            f"Reply tripped the failure phrase “{marker}”."
            if marker else "Reply tripped a failure marker."
        )
        return f"{base} Agent said: “{response}”" if response else base
    return detail or status


def _fmt_duration(seconds):
    if not seconds or seconds < 0:
        return "—"
    seconds = int(round(seconds))
    minutes, secs = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m&nbsp;{secs:02d}s"
    return f"{secs}s"


def _status_is_fail(status):
    return status in FAIL_STATUSES


def _load_all_results():
    """Return the latest generic row per test (all 55), preserving first-seen order.

    Fed by the conftest hook, which records one row per test with keys:
    nodeid, group, func, param, status (PASS/FAIL/ERROR/SKIP), duration, reason.
    """
    rows = {}
    if not os.path.exists(ALL_RESULTS_FILE):
        return []
    with open(ALL_RESULTS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            nodeid = row.get("nodeid")
            if nodeid:
                rows[nodeid] = row  # last wins; re-assign keeps first-seen position
    return list(rows.values())


def _pretty(text):
    return (text or "").replace("test_", "").replace("_", " ").strip()


def _generic_label(row):
    """Readable label for a non-Teams test: its param id, else the function name."""
    return row.get("param") or _pretty(row.get("func", ""))


def _generic_result_text(row):
    """Result cell for a non-Teams test row."""
    status = row.get("status")
    if status == "PASS":
        return "Passed."
    if status == "SKIP":
        return "Skipped."
    reason = _clean(row.get("reason", ""), limit=240)
    return html.escape(reason) if reason else html.escape(status or "Failed")


def _build_callout(fail_entries):
    """Failed-tests callout across every group (empty -> all-passed banner)."""
    if not fail_entries:
        return (
            '  <div class="sec-title">Failed Tests</div>\n'
            '  <div class="callout"><div class="fail-row">'
            '<div class="why"><div class="q">All tests passed \U0001f389</div></div>'
            "</div></div>\n"
        )
    rows = []
    for e in fail_entries:
        marker = html.escape((e["status"] or "").lower())
        reason = html.escape(e["reason"] or "")
        rows.append(
            f"""    <div class="fail-row">
      <div class="who">{html.escape(e['group'])}<span class="cap">{html.escape(e['label'])}</span></div>
      <div class="why">
        <div class="q">{reason} <span class="marker">{marker}</span></div>
      </div>
    </div>"""
        )
    return (
        '  <div class="sec-title"><span class="mark">✕</span> Failed Tests</div>\n'
        '  <div class="callout">\n' + "\n".join(rows) + "\n  </div>\n"
    )


def _build_card(title, entries, label_header):
    """One suite-group card: meter + pass ratio + a status/label/result table."""
    total = len(entries)
    passed = sum(1 for e in entries if not e["is_fail"] and e["status"] != "SKIP")
    pct = (passed / total * 100) if total else 0
    ratio_cls = " all-pass" if passed == total else ""

    body_rows = []
    for e in entries:
        pill_cls = "fail" if e["is_fail"] else "pass"
        pill_txt = "FAIL" if e["is_fail"] else ("SKIP" if e["status"] == "SKIP" else "PASS")
        tr_cls = ' class="is-fail"' if e["is_fail"] else ""
        body_rows.append(
            f'        <tr{tr_cls}><td><span class="pill {pill_cls}">{pill_txt}</span></td>'
            f'<td><span class="cap">{html.escape(e["label"])}</span></td>'
            f'<td class="result">{e["result"]}</td></tr>'
        )

    return (
        f"""  <div class="feature">
    <div class="feature-head">
      <h3>{html.escape(title)}</h3>
      <div class="meter"><span style="width:{pct:.4g}%"></span></div>
      <div class="ratio{ratio_cls}"><b>{passed}</b> / {total} passed</div>
    </div>
    <div class="table-scroll">
    <table>
      <thead><tr><th class="colst">Status</th><th class="colcap">{html.escape(label_header)}</th><th>Result</th></tr></thead>
      <tbody>
{chr(10).join(body_rows)}
      </tbody>
    </table>
    </div>
  </div>"""
    )


def generate_report(duration_seconds=None):
    """Render ``reports/teams_feature_report.html`` for the whole suite (all 55).

    Uses the generic per-test rows from the conftest hook (``all_results.jsonl``)
    for every group, overlaying the richer Teams data (``teams_results.jsonl``)
    on the Teams Feature section for capability labels and agent-reply context.

    Returns the report path, or ``None`` when there is no generic run data so a
    caller can skip quietly rather than overwrite a good report with an empty one.
    """
    generic = _load_all_results()
    if not generic:
        return None

    teams_rich = _load_latest_rows()  # {param name: rich Teams row}
    try:
        model = CommonUtils.read_json(DATA_FILE).get("model") or "Not pinned"
    except (OSError, ValueError):
        model = "Not pinned"

    # ---- Tiles (whole suite) --------------------------------------------------
    total = len(generic)
    passed = sum(1 for r in generic if r.get("status") == "PASS")
    skipped = sum(1 for r in generic if r.get("status") == "SKIP")
    failed = sum(1 for r in generic if r.get("status") in GENERIC_FAIL)
    overall = "FAILED" if failed else "PASSED"
    date_str = datetime.now().strftime("%A, %d %B %Y")
    total_duration = sum((r.get("duration") or 0) for r in generic) or duration_seconds

    # ---- Group rows, preserving order, ordered by GROUP_ORDER -----------------
    groups = {}
    for r in generic:
        groups.setdefault(r.get("group", "Other"), []).append(r)
    ordered = [g for g in GROUP_ORDER if g in groups] + [
        g for g in groups if g not in GROUP_ORDER
    ]

    def make_entry(r):
        status = r.get("status")
        entry = {
            "group": r.get("group", "Other"),
            "status": status,
            "is_fail": status in GENERIC_FAIL,
        }
        rich = teams_rich.get(r.get("param")) if entry["group"] == "Teams Feature" else None
        if rich:
            entry["label"] = rich.get("capability") or _generic_label(r)
            entry["result"] = _result_text(rich)
            entry["reason"] = _fail_reason(rich)
        else:
            entry["label"] = _generic_label(r)
            entry["result"] = _generic_result_text(r)
            entry["reason"] = _clean(r.get("reason", ""), limit=240)
        return entry

    entries_by_group = {g: [make_entry(r) for r in groups[g]] for g in ordered}

    fail_entries = [e for g in ordered for e in entries_by_group[g] if e["is_fail"]]
    callout = _build_callout(fail_entries)

    cards = [
        _build_card(
            g,
            entries_by_group[g],
            "Capability" if g == "Teams Feature" else "Test",
        )
        for g in ordered
    ]

    html_doc = _TEMPLATE.format(
        date=html.escape(date_str),
        overall=overall,
        model=html.escape(model),
        environment=html.escape(ENVIRONMENT),
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        duration=_fmt_duration(total_duration),
        callout=callout,
        features="\n\n".join(cards),
    )

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return REPORT_FILE


_TEMPLATE = """<title>Q-GPT Test Report</title>
<style>
  :root {{
    --ground: #f6f7f9; --surface: #ffffff; --surface-2: #f0f2f5;
    --ink: #191c22; --muted: #5f6976; --faint: #8a94a2;
    --border: #e3e7ec; --border-strong: #d3d9e0; --accent: #345a94;
    --pass: #12805c; --pass-bg: #e6f4ee; --fail: #cf3546; --fail-bg: #fbe9eb;
    --clarify: #9a6a12; --clarify-bg: #f6efdd;
    --head-a: #d8394a; --head-b: #b0283a; --on-head: #ffffff; --on-head-dim: rgba(255,255,255,.82);
    --shadow: 0 1px 2px rgba(20,25,35,.05), 0 6px 20px rgba(20,25,35,.06);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --ground: #13151a; --surface: #1b1e25; --surface-2: #232732;
      --ink: #e7eaee; --muted: #9aa4b2; --faint: #6f7887;
      --border: #2b303a; --border-strong: #3a404c; --accent: #7ea3dc;
      --pass: #37cc8d; --pass-bg: rgba(55,204,141,.13); --fail: #f3606f; --fail-bg: rgba(243,96,111,.14);
      --clarify: #d9ab5b; --clarify-bg: rgba(217,171,91,.13);
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  :root[data-theme="dark"] {{
    --ground: #13151a; --surface: #1b1e25; --surface-2: #232732;
    --ink: #e7eaee; --muted: #9aa4b2; --faint: #6f7887;
    --border: #2b303a; --border-strong: #3a404c; --accent: #7ea3dc;
    --pass: #37cc8d; --pass-bg: rgba(55,204,141,.13); --fail: #f3606f; --fail-bg: rgba(243,96,111,.14);
    --clarify: #d9ab5b; --clarify-bg: rgba(217,171,91,.13);
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--ground); color: var(--ink);
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 1060px; margin: 0 auto; padding: 28px 20px 72px; }}
  .banner {{ background: linear-gradient(135deg, var(--head-a), var(--head-b)); color: var(--on-head);
    border-radius: 14px; padding: 26px 30px; box-shadow: var(--shadow); }}
  .banner h1 {{ margin: 0; font-size: clamp(1.35rem, 2.4vw, 1.9rem); font-weight: 700; letter-spacing: -.01em; text-wrap: balance; }}
  .banner .meta {{ margin-top: 8px; font-size: .92rem; color: var(--on-head-dim);
    display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: center; }}
  .banner .meta strong {{ color: var(--on-head); font-weight: 700; letter-spacing: .02em; }}
  .dot {{ width: 4px; height: 4px; border-radius: 50%; background: var(--on-head-dim); display: inline-block; }}
  .tiles {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: var(--border);
    border: 1px solid var(--border); border-radius: 14px; overflow: hidden; margin-top: 18px; box-shadow: var(--shadow); }}
  .tile {{ background: var(--surface); padding: 20px 16px; text-align: center; }}
  .tile .num {{ font-size: clamp(1.7rem, 3.6vw, 2.5rem); font-weight: 700; letter-spacing: -.02em;
    font-variant-numeric: tabular-nums; line-height: 1; }}
  .tile .lbl {{ margin-top: 8px; font-size: .68rem; text-transform: uppercase; letter-spacing: .09em;
    color: var(--muted); font-weight: 600; }}
  .tile.pass .num {{ color: var(--pass); }}
  .tile.fail .num {{ color: var(--fail); }}
  @media (max-width: 720px) {{
    .tiles {{ grid-template-columns: repeat(3, 1fr); }}
    .tile:nth-child(4), .tile:nth-child(5) {{ border-top: 1px solid var(--border); }}
  }}
  .sec-title {{ display: flex; align-items: center; gap: 10px; margin: 34px 0 14px;
    font-size: 1.05rem; font-weight: 700; letter-spacing: -.01em; }}
  .sec-title .mark {{ color: var(--fail); font-size: 1.05rem; }}
  .callout {{ border: 1px solid var(--border); border-left: 3px solid var(--fail); background: var(--surface);
    border-radius: 10px; padding: 4px 0; box-shadow: var(--shadow); overflow: hidden; }}
  .fail-row {{ display: grid; grid-template-columns: 210px 1fr; gap: 4px 22px; padding: 16px 20px; }}
  .fail-row + .fail-row {{ border-top: 1px solid var(--border); }}
  .fail-row .who {{ font-weight: 600; }}
  .fail-row .who .cap {{ display: block; font-family: "Cascadia Code", Consolas, monospace; font-size: .78rem;
    color: var(--muted); font-weight: 500; margin-top: 3px; }}
  .fail-row .why .q {{ color: var(--ink); }}
  .fail-row .why .q em {{ color: var(--muted); font-style: normal; }}
  .marker {{ font-family: "Cascadia Code", Consolas, monospace; font-size: .78rem; background: var(--fail-bg);
    color: var(--fail); padding: 1px 7px; border-radius: 5px; white-space: nowrap; }}
  .fail-row .note {{ color: var(--muted); font-size: .9rem; margin-top: 6px; }}
  @media (max-width: 640px) {{ .fail-row {{ grid-template-columns: 1fr; }} }}
  .feature {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    box-shadow: var(--shadow); overflow: hidden; margin-top: 16px; }}
  .feature-head {{ display: flex; align-items: center; gap: 16px; padding: 15px 20px;
    border-bottom: 1px solid var(--border); background: var(--surface-2); }}
  .feature-head h3 {{ margin: 0; font-size: 1rem; font-weight: 700; flex: 0 0 auto; letter-spacing: -.01em; }}
  .meter {{ flex: 1 1 auto; height: 7px; border-radius: 4px; background: var(--fail); overflow: hidden;
    min-width: 80px; max-width: 340px; }}
  .meter > span {{ display: block; height: 100%; background: var(--pass); border-radius: 4px; }}
  .ratio {{ flex: 0 0 auto; font-size: .82rem; font-weight: 600; font-variant-numeric: tabular-nums; color: var(--muted); }}
  .ratio b {{ color: var(--ink); }}
  .ratio.all-pass b, .ratio.all-pass {{ color: var(--pass); }}
  table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
  thead th {{ text-align: left; font-size: .68rem; text-transform: uppercase; letter-spacing: .07em;
    color: var(--muted); font-weight: 600; padding: 10px 20px; border-bottom: 1px solid var(--border); }}
  tbody td {{ padding: 12px 20px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr.is-fail td:first-child {{ box-shadow: inset 3px 0 0 var(--fail); }}
  .cap {{ font-family: "Cascadia Code", Consolas, monospace; font-size: .8rem; color: var(--ink); }}
  .result {{ color: var(--muted); }}
  .pill {{ display: inline-flex; align-items: center; gap: 5px; font-size: .72rem; font-weight: 700;
    padding: 3px 9px; border-radius: 999px; letter-spacing: .02em; white-space: nowrap; }}
  .pill.pass {{ color: var(--pass); background: var(--pass-bg); }}
  .pill.fail {{ color: var(--fail); background: var(--fail-bg); }}
  .pill::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }}
  .colcap {{ width: 34%; }}
  .colst {{ width: 92px; }}
  @media (max-width: 640px) {{
    thead {{ display: none; }}
    tbody td {{ display: block; border-bottom: none; padding: 4px 18px; }}
    tbody tr {{ display: block; border-bottom: 1px solid var(--border); padding: 10px 0; }}
    .colcap {{ width: auto; }}
  }}
  footer {{ margin-top: 34px; color: var(--faint); font-size: .82rem; line-height: 1.7; }}
  footer code {{ font-family: "Cascadia Code", Consolas, monospace; font-size: .78rem; color: var(--muted); }}
  .table-scroll {{ overflow-x: auto; }}
</style>

<div class="wrap">

  <div class="banner">
    <h1>Q-GPT — Automated Test Report</h1>
    <div class="meta">
      <span>{date}</span>
      <span class="dot"></span>
      <span>Overall: <strong>{overall}</strong></span>
      <span class="dot"></span>
      <span>Model under test: <strong>{model}</strong></span>
      <span class="dot"></span>
      <span>Environment: <strong>{environment}</strong></span>
    </div>
  </div>

  <div class="tiles">
    <div class="tile"><div class="num">{total}</div><div class="lbl">Total</div></div>
    <div class="tile pass"><div class="num">{passed}</div><div class="lbl">Passed</div></div>
    <div class="tile fail"><div class="num">{failed}</div><div class="lbl">Failed</div></div>
    <div class="tile"><div class="num">{skipped}</div><div class="lbl">Skipped</div></div>
    <div class="tile"><div class="num">{duration}</div><div class="lbl">Duration</div></div>
  </div>

{callout}
  <div class="sec-title">Results by Suite</div>

{features}

  <footer>
    <p>Whole-suite report generated from the latest recorded run.
    Data: <code>reports/all_results.jsonl</code> (all tests) +
    <code>reports/teams_results.jsonl</code> (Teams detail)
    · builder: <code>utils/generate_teams_report.py</code>.</p>
  </footer>

</div>
"""


if __name__ == "__main__":
    path = generate_report()
    if path:
        print(f"Wrote {path}")
    else:
        print("No run data in reports/all_results.jsonl; run the suite first.")
