"""
Browser Driver Module

Manages Selenium WebDriver setup and provides generic browser automation utilities.
Simplified version with essential functionality only.
"""

import time
import random
import pickle
from pathlib import Path
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement

from src.utils.logger import app_logger


class BrowserDriver:
    """
    Manages Selenium WebDriver setup and generic browser actions.
    
    Provides a wrapper around Selenium WebDriver with utilities for:
    - Driver setup with configurable options
    - Cookie management for session persistence
    - Human-like interactions
    - Tab management
    - Element location and scrolling
    """
    
    def __init__(self, docker_env: bool = False, headless: bool = False):
        """
        Initialize BrowserDriver with environment settings.
        
        Args:
            docker_env: Whether to run in Docker environment
            headless: Whether to run in headless mode
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.docker_env = docker_env
        self.headless = headless
        self.logger = app_logger

    def setup_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome WebDriver with optimizations.
        
        Returns:
            Configured Chrome WebDriver instance
        """
        options = Options()
        
        # Essential options
        # Use a consistent screen size
        options.add_argument("--window-size=1080,720")

        # Disable extensions and infobars
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")  # Might not work on all Chrome versions

        # Required for Docker (even in non-headless mode)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
                
        # Performance optimizations
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Disable password manager and autofill
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Disable image loading for speed
            "credentials_enable_service": False,  # Disable Chrome's login popups
            "profile.password_manager_enabled": False,
            "autofill.profile_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        
        # Headless mode if specified
        if self.headless:
            print("Running in headless mode; browser GUI will NOT be visible.")
            options.add_argument("--headless=new")  # Use new headless mode
            options.add_argument("--disable-gpu")
        else:
            print("Running in non-headless mode; browser GUI will be visible.")
        
        # Create driver based on environment
        driver = None
        max_retries = 5
        retry_delay = 3  # seconds
        for attempt in range(max_retries):
            try:
                if self.docker_env:
                    driver = webdriver.Remote(
                        command_executor="http://selenium:4444/wd/hub",
                        options=options
                    )
                else:
                    driver = webdriver.Chrome(
                        service=Service(),
                        options=options
                    )
                break  # Success
            except Exception as e:  # Catch ConnectionRefusedError or similar
                self.logger.warning(f"Driver setup attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
            
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        self.logger.info("Browser driver initialized successfully")

        return driver


    def get(self, url: str):
        """
        Navigate to a URL.
        
        Args:
            url: The URL to navigate to
        """
        self.driver.get(url)
        self.logger.debug(f"Navigated to: {url}")

    def find_element(self, by: By, value: str, timeout: int = 10) -> WebElement:
        """
        Find a single element with explicit wait.
        
        Args:
            by: Locator strategy (e.g., By.CSS_SELECTOR)
            value: Locator value
            timeout: Maximum wait time in seconds
            
        Returns:
            WebElement if found
            
        Raises:
            TimeoutException if element not found within timeout
        """
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def find_elements(self, by: By, value: str, timeout: int = 10) -> List[WebElement]:
        """
        Find multiple elements with explicit wait.
        
        Args:
            by: Locator strategy
            value: Locator value
            timeout: Maximum wait time in seconds
            
        Returns:
            List of WebElements if found
            
        Raises:
            TimeoutException if no elements found within timeout
        """
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_all_elements_located((by, value))
        )

    def scroll(self, times: int = 1, default_key=Keys.DOWN):
        """
        Scroll the page with human-like behavior.
        
        Args:
            times: Number of scroll actions to perform
            default_key: Key to use for scrolling
        """
        try:
            body = self.find_element(By.CSS_SELECTOR, "body")
            for _ in range(times):
                body.send_keys(default_key)
                time.sleep(random.uniform(0.4, 1.0))
        except Exception as e:
            self.logger.warning(f"Scroll failed: {str(e)}")

    def scroll_to_element(self, element: WebElement):
        """
        Scroll to an element with human-like gradual scrolling.
        
        Args:
            element: WebElement to scroll to
        """
        try:
            # Get element position
            element_y = element.location["y"]
            window_height = self.driver.execute_script("return window.innerHeight")
            current_scroll = self.driver.execute_script("return window.scrollY")
            target_scroll = element_y - (window_height // 2)  # Center element

            # Gradual scrolling
            steps = 5
            scroll_step = (target_scroll - current_scroll) / steps
            
            for _ in range(steps):
                self.driver.execute_script(f"window.scrollBy(0, {scroll_step});")
                time.sleep(random.uniform(0.2, 0.5))
                
            # Ensure element is in view
            ActionChains(self.driver).scroll_to_element(element).perform()
            
        except Exception as e:
            self.logger.warning(f"Failed to scroll to element: {str(e)}")
            # Fallback to simple scroll
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)

    def hover_element(self, element: WebElement):
        """
        Hover over an element.
        
        Args:
            element: WebElement to hover over
        """
        ActionChains(self.driver).move_to_element(element).perform()
        time.sleep(random.uniform(0.3, 0.7))

    def type_with_delay(self, element: WebElement, text: str, enter_after: bool = True):
        """
        Simulate human-like typing with random delays.
        
        Args:
            element: WebElement to type into
            text: Text to type
            enter_after: Whether to press Enter after typing
        """
        element.clear()
        
        for char in text:
            if char == "\n":
                # Handle newlines with SHIFT+ENTER
                element.send_keys(Keys.SHIFT, Keys.ENTER)
                time.sleep(random.uniform(0.2, 0.4))
            else:
                element.send_keys(char)
                # Variable delay based on character type
                if char == " ":
                    time.sleep(random.uniform(0.1, 0.3))
                elif char in ".,!?":
                    time.sleep(random.uniform(0.2, 0.4))
                else:
                    time.sleep(random.uniform(0.05, 0.15))
                    
        if enter_after:
            time.sleep(random.uniform(0.3, 0.7))
            element.send_keys(Keys.ENTER)

    def open_new_tab(self, url: Optional[str] = None):
        """
        Open a new tab and optionally navigate to a URL.
        
        Args:
            url: Optional URL to navigate to in the new tab
        """
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        
        if url:
            self.get(url)
            
        self.logger.debug(f"Opened new tab{f' with URL: {url}' if url else ''}")

    def close_current_tab(self):
        """Close the current tab and switch to the previous tab."""
        if len(self.driver.window_handles) > 1:
            current_index = self.driver.window_handles.index(
                self.driver.current_window_handle
            )
            self.driver.close()
            
            # Switch to previous tab
            new_index = max(0, current_index - 1)
            self.driver.switch_to.window(self.driver.window_handles[new_index])
            self.logger.debug("Closed current tab and switched to previous")
        else:
            self.logger.warning("Cannot close the only open tab")

    def close_all_other_tabs(self):
        """Close all tabs except the first/main tab."""
        main_window = self.driver.window_handles[0]
        
        while len(self.driver.window_handles) > 1:
            self.driver.switch_to.window(self.driver.window_handles[-1])
            if self.driver.current_window_handle != main_window:
                self.driver.close()
                
        self.driver.switch_to.window(main_window)
        self.logger.debug("Closed all tabs except main")

    def save_cookies(self, filename: Path):
        """
        Save cookies to a file for session persistence.
        
        Args:
            filename: Path to save cookies to
        """
        filename.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filename, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)
            
        self.logger.info(f"Cookies saved to {filename}")

    def load_cookies(self, filename: Path) -> bool:
        """
        Load cookies from a file for session restoration.
        
        Args:
            filename: Path to cookies file
            
        Returns:
            True if cookies loaded successfully, False otherwise
        """
        if not filename.exists():
            self.logger.warning(f"Cookies file not found: {filename}")
            return False
            
        try:
            # Navigate to Facebook first
            self.driver.get("https://www.facebook.com")
            time.sleep(random.uniform(1, 2))
            
            # Load cookies
            with open(filename, "rb") as f:
                cookies = pickle.load(f)
            
            # Add valid cookies
            current_time = time.time()
            cookies_added = 0
            
            for cookie in cookies:
                # Check if cookie is for Facebook domain
                if 'domain' in cookie and 'facebook.com' in cookie['domain']:
                    # Check if not expired
                    if 'expiry' not in cookie or cookie['expiry'] > current_time:
                        try:
                            self.driver.add_cookie(cookie)
                            cookies_added += 1
                        except Exception as e:
                            self.logger.debug(f"Failed to add cookie: {e}")
                            
            self.logger.info(f"Loaded {cookies_added} cookies from {filename}")
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(random.uniform(2, 3))
            
            return cookies_added > 0
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {str(e)}")
            return False

    def take_screenshot(self, filename: str = None) -> str:
        """
        Take a screenshot of the current page.
        
        Args:
            filename: Optional filename for the screenshot
            
        Returns:
            Path to the saved screenshot
        """
        if filename is None:
            filename = f"screenshot_{int(time.time())}.png"
            
        filepath = Path("screenshots") / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        self.driver.save_screenshot(str(filepath))
        self.logger.info(f"Screenshot saved to {filepath}")
        
        return str(filepath)

    def wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: int = 10,
        condition: str = "presence"
    ) -> Optional[WebElement]:
        """
        Wait for an element with specified condition.
        
        Args:
            by: Locator strategy
            value: Locator value
            timeout: Maximum wait time
            condition: Wait condition ('presence', 'clickable', 'visible')
            
        Returns:
            WebElement if found, None otherwise
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            
            if condition == "clickable":
                element = wait.until(EC.element_to_be_clickable((by, value)))
            elif condition == "visible":
                element = wait.until(EC.visibility_of_element_located((by, value)))
            else:
                element = wait.until(EC.presence_of_element_located((by, value)))
                
            return element
            
        except Exception as e:
            self.logger.debug(f"Element not found: {value}")
            return None

    def execute_script(self, script: str, *args):
        """
        Execute JavaScript in the browser.
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script
            
        Returns:
            Result of script execution
        """
        return self.driver.execute_script(script, *args)

    def close(self):
        """Close the WebDriver and cleanup resources."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser driver closed")
            except Exception as e:
                self.logger.error(f"Error closing browser: {str(e)}")
            finally:
                self.driver = None