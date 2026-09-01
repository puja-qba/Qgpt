# Base class shared by every page object. Wraps the raw Playwright ``page``
# with small, reusable actions (click, type, read, wait) so the concrete
# page objects stay readable and don't repeat locator plumbing.
class BasePage:

    # Store the Playwright page handle that all actions below operate on.
    def __init__(self, page):
        self.page = page

    # Click the element identified by the given locator.
    def click_element(self, locator):
        self.page.locator(locator).click()

    # Type text into the element (clears any existing value first).
    def enter_text(self, locator, text):
        self.page.locator(locator).fill(text)

    # Return the visible text content of the element.
    def get_text(self, locator):
        return self.page.locator(locator).text_content()

    # Wait until the element is present, up to an optional timeout (ms).
    def wait_for_element(self, locator, timeout=None):
        self.page.locator(locator).wait_for(timeout=timeout)

    # Send a keyboard key (e.g. "Enter") to the element.
    def press_key(self, locator, key):
        self.page.locator(locator).press(key)

    # Return True if the element is currently visible on screen.
    def is_element_visible(self, locator):
        return self.page.locator(locator).is_visible()

    # Return True if the element is enabled (not disabled/greyed out).
    def is_element_enabled(self, locator):
        return self.page.locator(locator).is_enabled()
