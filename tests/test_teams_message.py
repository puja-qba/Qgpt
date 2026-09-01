import pytest
from playwright.sync_api import sync_playwright

from pages.login_page import LoginPage
from pages.agent_page import AgentPage
from utils.common import CommonUtils


# Load run config, login credentials, and the Teams message test data.
config = CommonUtils.read_json("config/config.json")
login_data = CommonUtils.read_json("data/input_data.json")
teams_data = CommonUtils.read_json("data/teams_message_data.json")


@pytest.fixture(scope="module")
def agent_session():
    """Log in once and hand back an AgentPage for the Teams message test."""
    # Start Playwright and read the browser/headless settings from config.
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

    # Open a fresh page and navigate to the app under test.
    page = browser.new_page()
    page.goto(config["base_url"])

    # Log in with valid credentials, just once for the whole module.
    login_page = LoginPage(page)
    username = login_data["valid_login"]["username"]
    password = login_data["valid_login"]["password"]
    login_page.login(username, password)

    # Fail fast if login didn't reach the dashboard.
    assert login_page.is_dashboard_visible(), "Login failed - dashboard not visible"

    agent_page = AgentPage(page)

    # Switch to the model under test (if one is configured) before querying.
    model = teams_data.get("model")
    if model:
        agent_page.select_model(model)
        assert model in agent_page.get_selected_model(), (
            f"Failed to switch model to {model!r}; "
            f"selector shows {agent_page.get_selected_model()!r}"
        )

    # Hand the ready AgentPage to the test, then tear the browser down after.
    yield agent_page

    browser.close()
    playwright.stop()


def test_send_teams_message_to_souvik(agent_session):
    """Ask the QGPT agent to send a Teams message to Souvik Behera via the
    Microsoft Teams integration, and verify it confirms the message was sent.
    """
    # Reuse the shared, already-logged-in agent page.
    agent_page = agent_session

    # Pull the recipient, the keyword expected in the reply, and success phrases.
    recipient = teams_data["recipient"]
    recipient_keyword = teams_data["recipient_keyword"]
    success_keywords = teams_data["success_keywords"]

    # Submit the "send message" query and wait for the agent's reply.
    agent_page.ask_query(teams_data["query"])
    agent_page.wait_for_response()

    # The reply must be non-empty.
    response = agent_page.get_response_text()
    assert response and response.strip(), "Agent returned an empty response"

    # The confirmation should name the recipient.
    assert recipient_keyword in response, (
        f"Expected recipient '{recipient_keyword}' in agent response for the "
        f"Teams message to {recipient!r}, got: {response!r}"
    )

    # And it should indicate the message was actually sent (any success phrasing).
    lowered = response.lower()
    assert any(kw.lower() in lowered for kw in success_keywords), (
        f"Agent did not confirm the Teams message was sent to {recipient!r}. "
        f"Expected one of {success_keywords}, got: {response!r}"
    )
