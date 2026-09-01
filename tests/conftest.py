import pytest
import os
import json
import time
from playwright.sync_api import sync_playwright
from utils.common import CommonUtils
from utils.generate_teams_report import generate_report


# Load the shared run config (browser, headless, base_url) used by fixtures below.
config = CommonUtils.read_json("config/config.json")

# Generic per-test results for ALL tests (every suite), consumed by the report
# generator to build the whole-suite (55-test) breakdown.
ALL_RESULTS_FILE = os.path.join("reports", "all_results.jsonl")

# Map test file -> human-readable suite group shown in the report.
_GROUPS = {
    "test_login": "Login",
    "test_agent_query": "Agent Query",
    "test_teams_feature": "Teams Feature",
    "test_teams_message": "Teams Message",
}

# Map pytest's raw outcome words to the short status labels used in the report.
_STATUS = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}


# Derive the report group name from a test's nodeid (file name -> suite group).
def _group_for(nodeid):
    fname = nodeid.split("::", 1)[0].rsplit("/", 1)[-1].replace(".py", "")
    return _GROUPS.get(fname, _pretty_group(fname))


# Fallback: turn an unknown "test_some_thing" file name into a readable "Some Thing".
def _pretty_group(fname):
    return fname.replace("test_", "").replace("_", " ").strip().title() or "Other"


def _parse_name(nodeid):
    """Split a nodeid's final part into (function, param-id)."""
    last = nodeid.split("::")[-1]
    if "[" in last:
        func, param = last.split("[", 1)
        return func, param.rstrip("]")
    return last, ""


def _short_reason(report):
    """Pull the final assertion/error line out of a failing test's traceback."""
    text = getattr(report, "longreprtext", "") or ""
    if not text and report.longrepr is not None:
        text = str(report.longrepr)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    e_lines = [ln[1:].strip() for ln in lines if ln.startswith("E ")]
    reason = (e_lines[-1] if e_lines else (lines[-1] if lines else "")).strip()
    return reason[:300]


def _record_generic(report, status):
    """Append one generic result row for any test. Never raises into the run."""
    try:
        func, param = _parse_name(report.nodeid)
        row = {
            "nodeid": report.nodeid,
            "group": _group_for(report.nodeid),
            "func": func,
            "param": param,
            "status": status,
            "duration": round(getattr(report, "duration", 0.0) or 0.0, 2),
            "reason": _short_reason(report) if status in ("FAIL", "ERROR") else "",
        }
        os.makedirs(os.path.dirname(ALL_RESULTS_FILE), exist_ok=True)
        with open(ALL_RESULTS_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # pragma: no cover - recording must never break the run
        pass


# Per-test fixture: launch a browser, hand the test a page, then clean up
# (capturing a screenshot on failure) after the test finishes.
@pytest.fixture(scope="function")
def setup(request):

    # Start Playwright and read the desired browser/headless settings.
    playwright = sync_playwright().start()

    browser_name = config["browser"]
    headless = config["headless"]

    # Launch the configured browser engine.
    if browser_name == "chromium":
        browser = playwright.chromium.launch(headless=headless)

    elif browser_name == "firefox":
        browser = playwright.firefox.launch(headless=headless)

    else:
        browser = playwright.webkit.launch(headless=headless)

    # Open a page and navigate to the app under test.
    page = browser.new_page()

    page.goto(config["base_url"])

    # Give the page to the test; everything below runs during teardown.
    yield page

    # On failure, save a screenshot named after the test for debugging.
    if request.node.rep_call.failed:

        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")

        screenshot_path = f"screenshots/{request.node.name}.png"

        page.screenshot(path=screenshot_path)

    # Always close the browser and stop Playwright.
    browser.close()
    playwright.stop()


# Hook that stashes each test phase's report on the item so the fixture above
# can check request.node.rep_call.failed during teardown.
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):

    outcome = yield
    rep = outcome.get_result()

    setattr(item, "rep_" + rep.when, rep)


def pytest_runtest_logreport(report):
    # Record one generic row per test for the whole-suite report. The "call"
    # phase covers normal pass/fail/skip; a non-passing "setup" phase catches
    # fixture errors/skips where the test body never runs (e.g. a failed login
    # fixture), which we mark ERROR/SKIP so those tests still appear.
    if report.when == "call":
        status = "PASS" if report.passed else ("SKIP" if report.skipped else "FAIL")
        _record_generic(report, status)
    elif report.when == "setup" and not report.passed:
        _record_generic(report, "SKIP" if report.skipped else "ERROR")


def pytest_sessionstart(session):
    # Stamp the start so pytest_sessionfinish can report a real run duration.
    session.config._run_start = time.time()


def pytest_sessionfinish(session, exitstatus):
    # Rebuild the customized Teams report from the latest recorded results after
    # every run. generate_report() returns None (and we stay quiet) when the run
    # touched no Teams scenarios, so a login-only run won't clobber the report.
    # Never let a reporting hiccup fail the test session.
    elapsed = time.time() - getattr(session.config, "_run_start", time.time())
    try:
        path = generate_report(duration_seconds=elapsed)
        if path:
            print(f"\n[teams-report] wrote {path}")
    except Exception as exc:  # pragma: no cover - reporting must never break the run
        print(f"\n[teams-report] skipped: {exc}")
