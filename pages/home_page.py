from pages.base_page import BasePage


# Page object for the home page. Exposes the top heading so tests can confirm
# they landed on the expected page after navigation/login.
class HomePage(BasePage):

    # Locator for the main page heading (the first <h1>).
    HOME_TEXT = "//h1"

    # Return the heading text so a test can assert the home page loaded.
    def verify_home_page(self):

        return self.get_text(self.HOME_TEXT)
