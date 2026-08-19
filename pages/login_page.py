from pages.base_page import BasePage
import time

class LoginPage(BasePage):

    USERNAME = "//input[@data-testid='email']"
    PASSWORD = "//input[@data-testid='password']"
    LOGIN_BUTTON = "//span[text()='Sign In']"
    DASHBOARD_TEXT = "//p[text()='Q-GPT Enterprise']"

    def login(self, username, password):
        self.enter_text(self.USERNAME, username)
        self.enter_text(self.PASSWORD, password)

        # The app disables Sign In until both fields are filled. Only click
        # when it is actually enabled; a disabled button means login is blocked.
        if self.is_element_enabled(self.LOGIN_BUTTON):
            self.click_element(self.LOGIN_BUTTON)

        time.sleep(5)

    
    def is_dashboard_visible(self):
        """
        Verify whether the Dashboard page is visible after login.

        This method checks the visibility of the Dashboard.
        element/text on the application home page.

        Used for validating successful user login.

        Returns:
            bool:
                True  -> Dashboard is visible
                False -> Dashboard is not visible
        """
        return self.is_element_visible(self.DASHBOARD_TEXT)