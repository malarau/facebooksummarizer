from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from src.config.config import Config
from src.browser.facebook_automation_workflow import BrowserDriver
from src.poster.facebook_poster import FacebookPoster
from src.utils.url_utils import URLUtils
from src.scraper.article import ArticleScraper
from src.utils.logger import app_logger
import time, random, os
from typing import List, Dict, Optional, Tuple
from retrying import retry

class FacebookScraper:
    """Handles Facebook login and post scraping."""
    CSS_SELECTOR_LOGIN_BUTTON = 'button[name="login"][data-testid="royal-login-button"]'
    XPATH_HUMAN_VERIFICATION = '//h2[@data-theme="home.title" and contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "verify") or contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "challenge") or contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "human")]'
    CSS_SELECTOR_EMAIL_FIELD = 'input#email'
    CSS_SELECTOR_NAVIGATION_BAR = 'div[aria-label="Facebook"][role="navigation"]'
    CSS_SELECTOR_ALL_POSTS = 'div[data-virtualized]'
    CSS_SELECTOR_POST_TEXT = 'div[data-ad-comet-preview="message"] div[dir="auto"]'
    CSS_SELECTOR_LINK_POST_TEXT = 'span.html-span[dir="auto"]'
    CSS_SELECTOR_AUTHOR_COMMENT = 'div[role="article"][aria-label][tabindex="-1"]'
    CSS_SELECTOR_AUTHOR_COMMENT_LINK = 'span[dir="auto"][lang]'
    CSS_SELECTOR_IMAGEPOST = 'div[class][style*="background-color"][style*="background-image"]'
    CSS_SELECTOR_POST_ID_ELEMENT = 'span > a[target="_blank"][role="link"]'
    CSS_SELECTOR_POST_ID_ON_HOVER = 'a[href*="/posts/"][role="link"]'

    def __init__(self, driver: BrowserDriver, is_testing: bool = False):
        self.driver = driver
        self.url_utils = URLUtils()
        self.is_testing = is_testing

    def login(self) -> bool:
        """Log in to Facebook with robust verification handling."""
        cookie_file = Config.COOKIE_DIR / f"{Config.FB_EMAIL.replace('@', '_at_').replace('.', '_dot_')}.pkl"
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            app_logger.info(f"Login attempt {attempt}/{max_attempts}")

            # Try loading cookies
            try:
                if cookie_file.exists():
                    try:
                        self.driver.load_cookies(cookie_file)
                        self.driver.get(Config.SOURCE_URL)
                        time.sleep(random.uniform(1, 2))

                        # Check if login is required (invalid session)
                        if self._is_login_prompt_present() or "two_step_verification" in self.driver.driver.current_url:
                            app_logger.warning("Invalid session detected; deleting cookies")
                            os.remove(cookie_file)
                        else:
                            # Verify login success
                            if self._is_login_successful():
                                app_logger.info("Login successful via cookies")
                                return True
                            app_logger.warning("Navigation bar not found; session invalid")
                            os.remove(cookie_file)
                    except Exception as e:
                        app_logger.warning(f"Cookie loading failed: {str(e)}")
                        if cookie_file.exists():
                            os.remove(cookie_file)

                # Perform fresh login
                self.driver.get(Config.SOURCE_URL)
                time.sleep(random.uniform(1, 2))

                # Check for login elements
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_LOGIN_BUTTON, timeout=Config.TIMEOUT)
                    email_field = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_EMAIL_FIELD)
                    password_field = self.driver.find_element(By.ID, "pass")
                except (TimeoutException, NoSuchElementException) as e:
                    app_logger.error(f"Login elements not found: {str(e)}")
                    continue

                # Enter credentials
                self.driver.type_with_delay(email_field, Config.FB_EMAIL, enter_after=False)
                time.sleep(random.uniform(0.5, 1.5))
                self.driver.type_with_delay(password_field, Config.FB_PASSWORD, enter_after=False)
                time.sleep(random.uniform(0.5, 1.5))
                button.click()
                self.driver.find_element(By.CSS_SELECTOR, "body").send_keys(Keys.ESCAPE)  # Dismiss password save prompt
                time.sleep(random.uniform(2, 3))

                # Check for human verification or login prompt
                for _ in range(2):  # Allow two verification attempts
                    if self._is_human_verification_present() or "two_step_verification" in self.driver.driver.current_url:
                        app_logger.warning("Human verification or two-step authentication detected")
                        app_logger.info("Pausing for 60 seconds to allow manual verification...")
                        time.sleep(1)  # Pause for manual interaction
                        if not (self._is_human_verification_present() or "two_step_verification" in self.driver.driver.current_url):
                            app_logger.info("Verification appears complete")
                            break
                    else:
                        break

                # Verify login success
                if self._is_login_successful():
                    self.driver.save_cookies(cookie_file)
                    app_logger.info("Login successful; cookies saved")
                    return True
                else:
                    app_logger.warning("Login failed: navigation bar not found")
                    if cookie_file.exists():
                        os.remove(cookie_file)
                    continue

            except Exception as e:
                app_logger.error(f"Login attempt failed: {str(e)}")
                if cookie_file.exists():
                    os.remove(cookie_file)
                continue

        app_logger.error(f"Login failed after {max_attempts} attempts")
        raise Exception(f"Login failed after {max_attempts} attempts")

    def _is_human_verification_present(self) -> bool:
        """Check for human verification prompts."""
        try:
            self.driver.find_element(By.XPATH, self.XPATH_HUMAN_VERIFICATION, timeout=3)
            app_logger.info("Human verification detected via XPath")
            return True
        except TimeoutException:
            return False

    def _is_login_prompt_present(self) -> bool:
        """Check for login prompt (email field or login button)."""
        try:
            self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_EMAIL_FIELD, timeout=3)
            app_logger.info("Login prompt detected via email field")
            return True
        except TimeoutException:
            try:
                self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_LOGIN_BUTTON, timeout=3)
                app_logger.info("Login prompt detected via login button")
                return True
            except TimeoutException:
                return False

    def _is_login_successful(self) -> bool:
        """Check if login was successful by looking for the navigation bar."""
        try:
            self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_NAVIGATION_BAR, timeout=5)
            app_logger.info("Navigation bar found; login successful")
            
            # Remove any pop-ups or modals that might interfere
            time.sleep(1)
            self.driver.find_element(By.CSS_SELECTOR, "body").send_keys(Keys.ESCAPE)
            return True
        except TimeoutException:
            # Fallback: Check for news feed or search bar
            try:
                self.driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]', timeout=3)
                app_logger.info("News feed found; login successful")
                return True
            except TimeoutException:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, 'input[aria-label="Search Facebook"]', timeout=3)
                    app_logger.info("Search bar found; login successful")
                    return True
                except TimeoutException:
                    app_logger.warning("No login success indicators found")
                    return False
                
    def scroll_page(self, times: int = 3) -> None:
        """Scroll the page to load more posts."""
        app_logger.info(f"Scrolling page {times} times")
        self.driver.scroll(times=times)
        time.sleep(random.uniform(1, 2))

    def select_posts(self) -> List:
        """Select all visible post elements on the page."""
        try:
            posts = self.driver.find_elements(By.CSS_SELECTOR, self.CSS_SELECTOR_ALL_POSTS, timeout=Config.TIMEOUT)
            app_logger.info(f"Selected {len(posts)} posts")
            return posts
        except TimeoutException:
            app_logger.warning("No posts found")
            return []

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def extract_post_id(self, post_element) -> Optional[str]:
        """Extract post ID by hovering over the post's link."""
        try:
            link_element = post_element.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_POST_ID_ELEMENT)
            self.driver.scroll_to_element(link_element)
            self.driver.scroll(times=3)
            self.driver.hover_element(link_element)
            time.sleep(random.uniform(0.5, 1.5))
            post_link_element = post_element.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_POST_ID_ON_HOVER, timeout=Config.TIMEOUT)
            post_link = post_link_element.get_attribute("href")
            post_id = self.url_utils.extract_post_id(post_link)
            if post_id:
                app_logger.info(f"Extracted post ID: {post_id}")
            else:
                app_logger.warning("Failed to extract post ID")
            return post_id
        except (NoSuchElementException, StaleElementReferenceException):
            app_logger.warning("Failed to extract post ID due to element issues")
            return None

    def scrape_posts(self, page_name: str, analyzer, poster, db) -> List[Dict]:
        self.driver.get(f"{Config.SOURCE_URL}{page_name}")
        time.sleep(random.uniform(2, 3))
        posts = []
        scroll_count = 0
        processed_ids = set()
        last_post_count = 0
        main_window = self.driver.driver.current_window_handle

        # Initial post loading
        max_initial_attempts = 3
        for attempt in range(max_initial_attempts):
            loaded_posts = self.select_posts()
            if loaded_posts:
                app_logger.info(f"Found {len(loaded_posts)} posts on attempt {attempt + 1}")
                break
            app_logger.info(f"No posts found on attempt {attempt + 1}; scrolling")
            self.scroll_page(times=2)
            time.sleep(random.uniform(1, 2))
        else:
            app_logger.warning(f"No posts loaded after {max_initial_attempts} attempts")
            return posts

        while len(posts) < Config.POST_LIMIT and scroll_count < Config.MAX_SCROLLS:
            scroll_count += 1
            app_logger.info(f"Scroll iteration {scroll_count}/{Config.MAX_SCROLLS}")

            loaded_posts = self.select_posts()
            if len(loaded_posts) == last_post_count and len(posts) < Config.POST_LIMIT:
                app_logger.info("No new posts; scrolling")
                self.scroll_page(times=2)
                time.sleep(random.uniform(1, 2))
                loaded_posts = self.select_posts()
                if len(loaded_posts) == last_post_count:
                    app_logger.warning("No new posts after scrolling; ending")
                    break

            for post in loaded_posts[last_post_count:]:
                last_post_count += 1
                try:
                    link_element = post.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_POST_ID_ELEMENT)
                    self.driver.scroll_to_element(link_element)
                    post_id = self.extract_post_id(post)
                    if not post_id or post_id in processed_ids:
                        continue
                    processed_ids.add(post_id)

                    # Open post in new tab
                    self.driver.open_new_tab(f"{Config.SOURCE_URL}{page_name}/posts/{post_id}")
                    app_logger.info(f"Processing post: {Config.SOURCE_URL}{page_name}/posts/{post_id}")

                    if self.is_testing or db.insert_post(post_id, page_name, 0):
                        post_data = self._scrape_single_post(None)
                        if not post_data or post_data["post_id"] != post_id:
                            self.driver.switch_to.window(main_window)
                            continue

                        # Analyze post
                        analysis = analyzer.analyze(
                            post_data["post_text"],
                            post_data["link_text"],
                            post_data["article_content"]
                        )
                        comment = f"Summary: {analysis['summary']}"
                        if analysis["is_clickbait"]:
                            comment += f"\nHidden Info: {analysis['hidden_info']}"

                        # Comment
                        if not self.is_testing:
                            self._scroll_to_comment_box(None)
                            if poster.comment_on_post(page_name, post_id, comment):
                                db.update_post_success(post_id, 1)
                            else:
                                app_logger.warning(f"Failed to comment on post {post_id}")

                        posts.append(post_data)
                        self.driver.switch_to.window(main_window)
                        self.driver.close_all_other_tabs(main_window)
                        if len(posts) >= Config.POST_LIMIT:
                            break
                except Exception as e:
                    app_logger.error(f"Error processing post {post_id}: {str(e)}")
                    self.driver.switch_to.window(main_window)
                    self.driver.close_all_other_tabs(main_window)
                    continue

        app_logger.info(f"Processed {len(posts)} posts from {page_name}")
        return posts

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def _scrape_single_post(self, post_element) -> Optional[Dict]:
        try:
            post_id = self.url_utils.extract_post_id(self.driver.driver.current_url) if not post_element else self.extract_post_id(post_element)
            if not post_id:
                return None

            # Post text
            try:
                post_text = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_POST_TEXT).text
            except NoSuchElementException:
                try:
                    post_text = self.driver.find_element(By.CSS_SELECTOR, 'div[role="article"] div[dir="auto"]').text
                except NoSuchElementException:
                    try:
                        div = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_IMAGEPOST)
                        post_text = div.text.replace("\n", "").replace(self.url_utils.extract_url(div.text) or "", "")
                    except NoSuchElementException:
                        post_text = "-"
                        app_logger.warning("Failed to extract post text")

            # Link text
            try:
                link_text = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_LINK_POST_TEXT).text
                if link_text == post_text:
                    link_text = "-"
            except NoSuchElementException:
                link_text = "-"

            # Article data
            try:
                article_url, article_content = self._get_article_data(None)
            except:
                article_url, article_content = None, None

            return {
                "post_id": post_id,
                "post_text": post_text,
                "link_text": link_text,
                "article_url": article_url,
                "article_content": article_content
            }
        except (StaleElementReferenceException, NoSuchElementException):
            app_logger.error("Failed to scrape post due to element issues")
            return None

    def _get_article_data(self, post_element) -> Tuple[Optional[str], Optional[str]]:
        article_scraper = ArticleScraper()
        main_window = self.driver.driver.current_window_handle
        try:
            # Post text for URL
            try:
                post_text = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_POST_TEXT).text
            except NoSuchElementException:
                try:
                    post_text = self.driver.find_element(By.CSS_SELECTOR, 'div[role="article"] div[dir="auto"]').text
                except NoSuchElementException:
                    try:
                        div = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_IMAGEPOST)
                        post_text = div.text.replace("\n", "").replace(self.url_utils.extract_url(div.text) or "", "")
                    except NoSuchElementException:
                        post_text = ""
                        app_logger.warning("Failed to extract post text for article URL")

            # Article URL
            try:
                link_element = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_LINK_POST_TEXT)
                self.driver.scroll_to_element(link_element)
                self.driver.hover_element(link_element)
                article_url = link_element.get_attribute("href")
                if not self.url_utils.is_valid_url(article_url):
                    article_url = None
            except NoSuchElementException:
                try:
                    link_element = self.driver.find_element(By.CSS_SELECTOR, 'a[href*="http"][role="link"]')
                    article_url = link_element.get_attribute("href")
                    if not self.url_utils.is_valid_url(article_url):
                        article_url = None
                except NoSuchElementException:
                    article_url = self.url_utils.extract_url(post_text)
                    if not article_url:
                        try:
                            div = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SELECTOR_IMAGEPOST)
                            article_url = self.url_utils.extract_url(div.text)
                        except NoSuchElementException:
                            article_url = None

            if not article_url:
                app_logger.warning("No article URL found")
                return None, None

            # Open article
            self.driver.open_new_tab(article_url)
            time.sleep(random.uniform(1, 2))
            article_content = article_scraper.scrape_article(self.driver.driver.current_url)
            self.driver.switch_to.window(main_window)
            self.driver.close_all_other_tabs(main_window)
            return article_url, article_content
        except Exception as e:
            app_logger.error(f"Error extracting article data: {str(e)}")
            self.driver.switch_to.window(main_window)
            self.driver.close_all_other_tabs(main_window)
            return None, None

    def _scroll_to_comment_box(self, post_element):
        """Scroll to the comment box to ensure it's interactable."""
        try:
            comment_box = post_element.find_element(By.CSS_SELECTOR, FacebookPoster.CSS_SELECTOR_COMMENT_BOX)
            self.driver.scroll_to_element(comment_box)
            self.driver.hover_element(comment_box)
            time.sleep(random.uniform(0.5, 1.5))
        except NoSuchElementException:
            app_logger.warning("Comment box not found for post")

    def open_post_in_new_tab(self, page_name: str, post_id: str) -> bool:
        """Open a post's URL in a new tab."""
        try:
            post_url = f"{Config.SOURCE_URL}{page_name}/posts/{post_id}"
            app_logger.info(f"Opening post URL in new tab: {post_url}")
            self.driver.open_new_tab(post_url)
            time.sleep(random.uniform(1, 2))
            return True
        except Exception as e:
            app_logger.error(f"Failed to open post URL: {str(e)}")
            return False