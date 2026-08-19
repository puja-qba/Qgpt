from pages.login_page import LoginPage
from pages.home_page import HomePage
from utils.common import CommonUtils
import time


test_data = CommonUtils.read_json("data/input_data.json")


def test_valid_login(setup):

    page = setup

    login_page = LoginPage(page)

    username = test_data["valid_login"]["username"]
    password = test_data["valid_login"]["password"]

    login_page.login(username, password)

    home_page = HomePage(page)

    # assert "Home" in home_page.verify_home_page()


def test_invalid_username_login(setup):

    page = setup

    login_page = LoginPage(page)

    username = test_data["invalid_username_login"]["username"]
    password = test_data["invalid_username_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


def test_without_username_login(setup):

    page = setup

    login_page = LoginPage(page)

    username = test_data["without_username_login"]["username"]
    password = test_data["without_username_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


def test_invalid_password_login(setup):

    page = setup

    login_page = LoginPage(page)

    username = test_data["invalid_password_login"]["username"]
    password = test_data["invalid_password_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()


def test_without_password_login(setup):

    page = setup

    login_page = LoginPage(page)

    username = test_data["without_password_login"]["username"]
    password = test_data["without_password_login"]["password"]

    # Perform Login
    login_page.login(username, password)
    time.sleep(5)

    # Dashboard Assertion
    assert not login_page.is_dashboard_visible()
