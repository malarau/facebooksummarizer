import time
from selenium.webdriver.common.by import By
from src.config.config import Config
from src.browser.facebook_automation_workflow import BrowserDriver

class FacebookPoster:
    """Posts comments to Facebook."""
    CSS_SELECTOR_COMMENT_BOX = 'div[role="textbox"][contenteditable="true"].notranslate'

    def __init__(self, driver: BrowserDriver):
        self.driver = driver

    def comment_on_post(self, page_name: str, post_id: str, comment: str) -> bool:
        """Comment on a specific post."""
        try:
            self.driver.open_new_tab(f"{Config.SOURCE_URL}{page_name}/posts/{post_id}")
            time.sleep(1)
            comment_box = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_COMMENT_BOX)
            self.driver.type_with_delay(comment_box, comment)
            self.driver.close_all_other_tabs()
            return True
        except Exception as e:
            self.driver.close_all_other_tabs()
            raise Exception(f"Failed to comment: {str(e)}")