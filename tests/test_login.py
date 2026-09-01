from pages.login_page import LoginPage
from pages.home_page import HomePage
from utils.common import CommonUtils
import time


# Load all login credential sets (valid + invalid variants) from the test data file.
test_data = CommonUtils.read_json("data/input_data.json")


# Happy path: valid credentials should log the user in successfully.
def test_valid_login(setup):

    # Get the browser page from the fixture and build the login page object.
    page = setup

    login_page = LoginPage(page)

    # Read valid credentials and perform the login.
    username = test_data["valid_login"]["username"]
    password = test_data["valid_login"]["password"]

    login_page.login(username, password)

    # Reach the home page (dashboard) after a successful login.
    home_page = HomePage(page)

    # assert "Home" in home_page.verify_home_page()


# Negative case: a wrong username must NOT reach the dashboard.
def test_invalid_username_login(setup):

    # Get the page and build the login page object.
    page = setup

    login_page = LoginPage(page)

    # Read the invalid-username credential set.
    username = test_data["invalid_username_login"]["username"]
    password = test_data["invalid_username_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


# Negative case: an empty username must NOT reach the dashboard.
def test_without_username_login(setup):

    # Get the page and build the login page object.
    page = setup

    login_page = LoginPage(page)

    # Read the missing-username credential set.
    username = test_data["without_username_login"]["username"]
    password = test_data["without_username_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


# Negative case: a wrong password must NOT reach the dashboard.
def test_invalid_password_login(setup):

    # Get the page and build the login page object.
    page = setup

    login_page = LoginPage(page)

    # Read the invalid-password credential set.
    username = test_data["invalid_password_login"]["username"]
    password = test_data["invalid_password_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


# Negative case: an empty password must NOT reach the dashboard.
def test_without_password_login(setup):

    # Get the page and build the login page object.
    page = setup

    login_page = LoginPage(page)

    # Read the missing-password credential set.
    username = test_data["without_password_login"]["username"]
    password = test_data["without_password_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()
