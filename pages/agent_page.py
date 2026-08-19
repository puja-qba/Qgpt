import time

from pages.base_page import BasePage


class AgentPage(BasePage):
    """Page object for the Q-GPT chat/agent screen shown after login."""

    CHAT_INPUT = "#onyx-chat-input-textarea"
    AI_MESSAGE = "//div[@data-testid='onyx-ai-message']"
    MODEL_SELECTOR = "[data-testid='model-selector']"
    MODEL_SEARCH_PLACEHOLDER = "Search models"

    def get_selected_model(self):
        """Return the label of the currently selected model (e.g. 'GLM 5.2')."""
        return (self.page.locator(self.MODEL_SELECTOR).text_content() or "").strip()

    def select_model(self, model_name):
        """Open the model dropdown, search for a model and select it.

        ``model_name`` must match the label shown in the dropdown result
        (e.g. 'GPT-5.5 Pro'). Raises if the model does not appear.
        """
        self.page.locator(self.MODEL_SELECTOR).click()
        search = self.page.get_by_placeholder(self.MODEL_SEARCH_PLACEHOLDER)
        search.wait_for(state="visible", timeout=15000)
        search.fill(model_name)

        result = self.page.get_by_text(model_name, exact=True)
        result.first.wait_for(state="visible", timeout=15000)
        result.first.click()

        # Wait until the selector label reflects the chosen model.
        self.page.wait_for_function(
            "([selector, name]) =>"
            " document.querySelector(selector)"
            " && document.querySelector(selector).textContent.includes(name)",
            arg=[self.MODEL_SELECTOR, model_name],
            timeout=15000,
        )

    def ask_query(self, query):
        """Type a query into the chat box and submit it with Enter.

        Records how many agent replies already exist so ``wait_for_response``
        can wait for the *new* reply rather than an earlier one still on screen
        (the chat accumulates messages across turns in a shared session).
        """
        self.wait_for_element(self.CHAT_INPUT, timeout=30000)
        self._message_count_before = self.page.locator(self.AI_MESSAGE).count()
        self.enter_text(self.CHAT_INPUT, query)
        self.press_key(self.CHAT_INPUT, "Enter")

    def wait_for_response(self, timeout=120000):
        """Wait for the new agent reply to appear and its streamed text to settle.

        The reply streams in token by token, so we first wait for a brand-new
        message to be added, then poll until its text stops changing.
        """
        baseline = getattr(self, "_message_count_before", 0)

        # Wait for a new agent message to be appended beyond what existed
        # before the query was submitted.
        self.page.wait_for_function(
            "([selector, baseline]) =>"
            " document.evaluate(selector, document, null, 7, null).snapshotLength"
            " > baseline",
            arg=[self.AI_MESSAGE, baseline],
            timeout=timeout,
        )

        self.page.locator(self.AI_MESSAGE).last.wait_for(
            state="visible", timeout=timeout
        )

        deadline = time.time() + (timeout / 1000)
        previous = None
        stable_since = None
        while time.time() < deadline:
            current = self.get_response_text() or ""
            if current and current == previous:
                # Text unchanged for ~2s -> streaming is done.
                if stable_since and (time.time() - stable_since) >= 2:
                    return
            else:
                stable_since = time.time()
            previous = current
            time.sleep(0.5)

    def get_response_text(self):
        """Return the text of the latest agent reply."""
        return self.page.locator(self.AI_MESSAGE).last.text_content()

    def is_response_visible(self):
        return self.page.locator(self.AI_MESSAGE).last.is_visible()
