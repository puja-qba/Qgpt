from pages.base_page import BasePage


class HomePage(BasePage):

    HOME_TEXT = "//h1"

    def verify_home_page(self):

        return self.get_text(self.HOME_TEXT)
