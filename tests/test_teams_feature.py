import json
import os
import time

import pytest
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.login_page import LoginPage
from pages.agent_page import AgentPage
from utils.common import CommonUtils


# Teams tool-calls (agent reasoning + MCP call + Graph API) can be slow, so we
# allow more than the 120s default before treating a missing reply as a failure.
RESPONSE_TIMEOUT = 180000

# Per-scenario outcomes are appended here so the run produces a readable
# working / not-working breakdown instead of only pytest pass/fail lines.
RESULTS_FILE = os.path.join("reports", "teams_results.jsonl")


def _record_result(scenario, status, detail, response="", duration=None):
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    row = {
        "name": scenario["name"],
        "category": scenario["category"],
        "capability": scenario["capability"],
        "status": status,
        "detail": detail,
        # Per-scenario wall time in seconds; summed by the report generator so
        # the Duration tile is accurate and survives a manual regenerate.
        "duration": round(duration, 2) if duration is not None else None,
        "response": (response or "")[:600],
    }
    with open(RESULTS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


config = CommonUtils.read_json("config/config.json")
login_data = CommonUtils.read_json("data/input_data.json")
teams_data = CommonUtils.read_json("data/teams_feature_data.json")


@pytest.fixture(scope="module")
def agent_session():
    """Log in once and hand back an AgentPage reused across all Teams scenarios.

    The Teams MCP integration must already be authenticated for the QGPT
    account under test; these scenarios drive the agent's Teams tools.
    """
    playwright = sync_playwright().start()

    browser_name = config["browser"]
    headless = config["headless"]

    if browser_name == "chromium":
        browser = playwright.chromium.launch(headless=headless)
    elif browser_name == "firefox":
        browser = playwright.firefox.launch(headless=headless)
    else:
        browser = playwright.webkit.launch(headless=headless)

    page = browser.new_page()
    # SPA keeps persistent connections open, so the full "load" event can hang;
    # wait for DOM content instead, which fires reliably on staging.
    page.goto(config["base_url"], wait_until="domcontentloaded", timeout=60000)

    login_page = LoginPage(page)
    username = login_data["valid_login"]["username"]
    password = login_data["valid_login"]["password"]
    login_page.login(username, password)

    assert login_page.is_dashboard_visible(), "Login failed - dashboard not visible"

    agent_page = AgentPage(page)

    model = teams_data.get("model")
    if model:
        agent_page.select_model(model)
        assert model in agent_page.get_selected_model(), (
            f"Failed to switch model to {model!r}; "
            f"selector shows {agent_page.get_selected_model()!r}"
        )

    yield agent_page

    browser.close()
    playwright.stop()


@pytest.mark.parametrize(
    "scenario",
    teams_data["scenarios"],
    ids=[s["name"] for s in teams_data["scenarios"]],
)
def test_teams_capability(agent_session, scenario):
    """Drive one Teams capability through the agent and verify the reply.

    A scenario passes when the agent returns a non-empty reply that
    (a) contains no hard failure marker (e.g. not-authenticated / error), and
    (b) contains at least one expected keyword for that capability. For
    state-dependent actions (edit/delete/react on an unspecified message) the
    expected keywords also accept a clarifying question as a valid reply.
    """
    agent_page = agent_session

    query = scenario["query"]
    expect_any = scenario["expect_any"]
    fail_markers = teams_data.get("fail_markers", [])

    start = time.time()
    agent_page.ask_query(query)

    try:
        agent_page.wait_for_response(timeout=RESPONSE_TIMEOUT)
    except PlaywrightTimeoutError:
        _record_result(
            scenario, "NO_RESPONSE",
            f"No reply within {RESPONSE_TIMEOUT // 1000}s",
            duration=time.time() - start,
        )
        pytest.fail(
            f"[{scenario['capability']}] No agent reply within "
            f"{RESPONSE_TIMEOUT // 1000}s for query {query!r}"
        )

    response = agent_page.get_response_text() or ""
    if not response.strip():
        _record_result(scenario, "EMPTY", "Empty response", duration=time.time() - start)
        pytest.fail(f"[{scenario['capability']}] Agent returned an empty response")

    lowered = response.lower()

    hit_fail = next((m for m in fail_markers if m.lower() in lowered), None)
    if hit_fail is not None:
        _record_result(scenario, "FAIL_MARKER", f"marker: {hit_fail}", response, duration=time.time() - start)
        pytest.fail(
            f"[{scenario['capability']}] Agent reply signals failure "
            f"('{hit_fail}') for query {query!r}, got: {response!r}"
        )

    matched = next((kw for kw in expect_any if kw.lower() in lowered), None)
    if matched is None:
        _record_result(scenario, "NO_KEYWORD", f"expected one of {expect_any}", response, duration=time.time() - start)
        pytest.fail(
            f"[{scenario['capability']}] Expected one of {expect_any} in agent "
            f"reply for query {query!r}, got: {response!r}"
        )

    _record_result(scenario, "PASS", f"matched: {matched}", response, duration=time.time() - start)
