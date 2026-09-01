from pages.base_page import BasePage
import time

# Page object for the login screen: fills credentials, submits, and checks
# whether login succeeded by looking for the post-login dashboard.
class LoginPage(BasePage):

    # Locators for the login form fields, the submit button, and a dashboard
    # element used to confirm a successful login.
    USERNAME = "//input[@data-testid='email']"
    PASSWORD = "//input[@data-testid='password']"
    LOGIN_BUTTON = "//span[text()='Sign In']"
    DASHBOARD_TEXT = "//p[text()='Q-GPT Enterprise']"

    # Enter the username/password, submit the form, and wait for the app to react.
    def login(self, username, password):
        # Fill in the credential fields.
        self.enter_text(self.USERNAME, username)
        self.enter_text(self.PASSWORD, password)

        # The app disables Sign In until both fields are filled. Only click
        # when it is actually enabled; a disabled button means login is blocked.
        if self.is_element_enabled(self.LOGIN_BUTTON):
            self.click_element(self.LOGIN_BUTTON)

        # Give the app time to process the login and load the next page.
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