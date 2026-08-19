import re

import pytest
from playwright.sync_api import sync_playwright

from pages.login_page import LoginPage
from pages.agent_page import AgentPage
from utils.common import CommonUtils


def _response_contains(response, keyword):
    """True if ``keyword`` appears in ``response``, tolerant of thousands separators.

    The agent formats large numbers with commas (e.g. "1,210"), so a bare
    "1210" keyword would otherwise miss. Strip commas that sit between digits
    before comparing; non-numeric keywords are unaffected.
    """
    if keyword in response:
        return True
    normalized = re.sub(r"(?<=\d),(?=\d)", "", response)
    return keyword in normalized


config = CommonUtils.read_json("config/config.json")
login_data = CommonUtils.read_json("data/input_data.json")
agent_data = CommonUtils.read_json("data/agent_query_data.json")


@pytest.fixture(scope="module")
def agent_session():
    """Log in once and hand back an AgentPage reused across all queries."""
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
    page.goto(config["base_url"])

    # Log in with valid credentials, just once for the whole module.
    login_page = LoginPage(page)
    username = login_data["valid_login"]["username"]
    password = login_data["valid_login"]["password"]
    login_page.login(username, password)

    assert login_page.is_dashboard_visible(), "Login failed - dashboard not visible"

    agent_page = AgentPage(page)

    # Switch to the model under test (if one is configured) before querying.
    model = agent_data.get("model")
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
    "case",
    agent_data["queries"],
    ids=[case["name"] for case in agent_data["queries"]],
)
def test_ask_query_to_agent(agent_session, case):
    agent_page = agent_session

    query = case["query"]
    expected_keyword = case["expected_keyword"]

    agent_page.ask_query(query)
    agent_page.wait_for_response()

    # Assert the agent returned a non-empty, relevant response.
    response = agent_page.get_response_text()
    assert response and response.strip(), "Agent returned an empty response"
    assert _response_contains(response, expected_keyword), (
        f"Expected '{expected_keyword}' in agent response for query "
        f"{query!r}, got: {response!r}"
    )
