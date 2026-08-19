class BasePage:

    def __init__(self, page):
        self.page = page

    def click_element(self, locator):
        self.page.locator(locator).click()

    def enter_text(self, locator, text):
        self.page.locator(locator).fill(text)

    def get_text(self, locator):
        return self.page.locator(locator).text_content()

    def wait_for_element(self, locator, timeout=None):
        self.page.locator(locator).wait_for(timeout=timeout)

    def press_key(self, locator, key):
        self.page.locator(locator).press(key)

    def is_element_visible(self, locator):
        return self.page.locator(locator).is_visible()

    def is_element_enabled(self, locator):
        return self.page.locator(locator).is_enabled()
