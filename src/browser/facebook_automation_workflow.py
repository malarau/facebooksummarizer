"""
Facebook Automation Workflow Module

This module provides an automated workflow for Facebook post analysis and commenting.
It scrapes posts, analyzes linked articles, and posts intelligent comments based on
content analysis (clickbait detection and summarization).
"""

import threading
import time
import random
import logging
import os
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from src.browser.driver import BrowserDriver
from src.scraper.facebook import FacebookScraper
from src.scraper.article import ArticleScraper
from src.analyzer.text_analyzer import TextAnalyzer
from src.poster.facebook_poster import FacebookPoster
from db.facebook_database import FacebookDatabase
from src.config.config import Config
from src.utils.logger import app_logger

# Load environment variables
load_dotenv()


class PostExtractionStrategy(Enum):
    """Strategies for extracting article URLs from posts."""
    POST_CARD = "post_card"
    POST_TEXT = "post_text"
    COMMENT_SECTION = "comment_section"


@dataclass
class PostData:
    """Data container for Facebook post information."""
    post_id: Optional[str] = None
    post_text: Optional[str] = None
    article_url: Optional[str] = None
    article_text: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    page_name: Optional[str] = None
    timestamp: Optional[float] = None


class FacebookConfig:
    """Configuration manager for Facebook automation."""
    
    def __init__(self):
        """Load configuration from environment variables."""
        # Facebook credentials
        self.fb_email = os.getenv('FB_EMAIL')
        self.fb_password = os.getenv('FB_PASSWORD')
        
        # Pages to scrape
        pages_str = os.getenv('FACEBOOK_PAGES', 'redgol,adncl')
        self.facebook_pages = [p.strip() for p in pages_str.split(',')]
        
        # OpenRouter API
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.openrouter_model = os.getenv('OPENROUTER_MODEL', 'gpt-3.5-turbo')
        
        # Automation settings
        self.max_posts_per_page = int(os.getenv('MAX_POSTS_PER_PAGE', '5'))
        self.run_interval_minutes = int(os.getenv('RUN_INTERVAL_MINUTES', '60'))
        self.enable_comments = os.getenv('ENABLE_COMMENTS', 'true').lower() == 'true'
        self.headless_mode = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'
        self.docker_env = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
        
        # Delays and timeouts
        self.min_delay_seconds = float(os.getenv('MIN_DELAY_SECONDS', '1'))
        self.max_delay_seconds = float(os.getenv('MAX_DELAY_SECONDS', '3'))
        self.page_load_timeout = int(os.getenv('PAGE_LOAD_TIMEOUT', '30'))
        
        # Database settings
        self.save_to_database = os.getenv('SAVE_TO_DATABASE', 'true').lower() == 'true'
        
        # Validate required settings
        self._validate()
    
    def _validate(self):
        """Validate required configuration."""
        if not self.fb_email or not self.fb_password:
            raise ValueError("FB_EMAIL and FB_PASSWORD must be set in .env file")
        
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY must be set in .env file")
        
        if not self.facebook_pages:
            raise ValueError("FACEBOOK_PAGES must be set in .env file")


class FacebookAutomationWorkflow:
    """
    Orchestrates the complete Facebook automation workflow.
    
    This class manages the entire process of:
    1. Logging into Facebook
    2. Navigating to target pages
    3. Extracting post information
    4. Analyzing linked articles
    5. Posting intelligent comments
    
    Attributes:
        config: FacebookConfig instance with settings
        browser: BrowserDriver instance for web automation
        scraper: FacebookScraper for post extraction
        analyzer: TextAnalyzer for content analysis
        poster: FacebookPoster for comment posting
        article_scraper: ArticleScraper for article extraction
        db: FacebookDatabase for data persistence
    """
    
    def __init__(self, config: Optional[FacebookConfig] = None, shutdown_event: threading.Event = None):
        """
        Initialize the Facebook automation workflow.
        
        Args:
            config: Optional FacebookConfig instance (creates new if None)
        """
        self.logger = app_logger or logging.getLogger(__name__)
        self.config = config or FacebookConfig()
        self.shutdown_event = shutdown_event
        
        # Initialize browser with config settings
        self.browser = BrowserDriver(
            docker_env=self.config.docker_env,
            headless=self.config.headless_mode
        )
        # Set up the browser driver
        self.browser.driver = self.browser.setup_driver()

        self.logger.info("Is self.browser a NoneType? " + str(self.browser is None))
        
        # Initialize components
        self.scraper = FacebookScraper(self.browser, is_testing=False)
        self.analyzer = TextAnalyzer()
        self.poster = FacebookPoster(self.browser)
        self.article_scraper = ArticleScraper()
        self.db = FacebookDatabase() if self.config.save_to_database else None
        
        # Configuration
        self.max_scroll_attempts = 3
        self.max_initial_post_attempts = 3
        self.min_posts_required = 1
        
        # Set credentials in scraper
        self.scraper.username = self.config.fb_email
        self.scraper.password = self.config.fb_password
        
    def run_workflow(
        self, 
        page_names: Optional[List[str]] = None,
        max_posts_per_page: Optional[int] = None,
        comment_on_posts: Optional[bool] = None
    ) -> List[PostData]:
        """
        Execute the complete automation workflow.
        
        Args:
            page_names: List of Facebook page names (uses config if None)
            max_posts_per_page: Maximum posts to process per page (uses config if None)
            comment_on_posts: Whether to post comments (uses config if None)
            
        Returns:
            List of PostData objects with processed information
            
        Raises:
            RuntimeError: If login fails or critical error occurs
        """
        # Use config defaults if not specified
        page_names = page_names or self.config.facebook_pages
        max_posts_per_page = max_posts_per_page or self.config.max_posts_per_page
        comment_on_posts = comment_on_posts if comment_on_posts is not None else self.config.enable_comments
        
        results = []
        
        try:
            # Step 1: Login
            if not self._login():
                raise RuntimeError("Failed to login to Facebook")
            
            # Step 2: Process each page
            for page_name in page_names:

                # Check for shutdown signal
                if self.shutdown_event.is_set():
                    self.logger.info("Shutdown requested - terminating page processing")
                    return results

                self.logger.info(f"Processing page: {page_name}")
                page_results = self._process_page(
                    page_name, 
                    max_posts_per_page,
                    comment_on_posts
                )
                results.extend(page_results)
                
                # Add delay between pages
                if page_name != page_names[-1]:
                    self._wait_random(5, 10)
                
        except Exception as e:
            self.logger.error(f"Workflow failed: {str(e)}")
            raise
            
        return results
    
    def _login(self) -> bool:
        """
        Login to Facebook using credentials from config.
        
        Returns:
            True if login successful, False otherwise
        """
        self.logger.info("Attempting Facebook login...")
        try:
            if self.scraper.login():
                self.logger.info("Login successful!")
                return True
            else:
                self.logger.error("Login failed")
                return False
        except Exception as e:
            self.logger.error(f"Login error: {str(e)}")
            return False
    
    def _process_page(
        self, 
        page_name: str,
        max_posts: int,
        comment_on_posts: bool
    ) -> List[PostData]:
        """
        Process a single Facebook page.
        
        Args:
            page_name: Name of the Facebook page
            max_posts: Maximum number of posts to process
            comment_on_posts: Whether to comment on posts
            
        Returns:
            List of PostData objects for processed posts
        """
        results = []
        
        try:
            # Navigate to page
            page_url = f"{Config.SOURCE_URL}{page_name}"
            self.browser.get(page_url)
            self._wait_random(
                self.config.min_delay_seconds,
                self.config.max_delay_seconds
            )
            self.logger.info(f"Navigated to {page_url}")
            
            # Load posts
            posts = self._load_initial_posts()
            if not posts:
                self.logger.warning(f"No posts found on page {page_name}")
                return results
            
            # Process posts
            processed_count = 0
            processed_ids = set()
            
            for i, post in enumerate(posts):

                # Check for shutdown signal
                if self.shutdown_event.is_set():
                    self.logger.info("Shutdown requested - terminating page processing")
                    return results

                if processed_count >= max_posts:
                    break
                    
                self.logger.info(f"Processing post {i+1}/{len(posts)}")
                post_data = self._process_single_post(
                    post, 
                    page_name,
                    comment_on_posts
                )
                
                if post_data and post_data.post_id and post_data.post_id not in processed_ids:
                    post_data.timestamp = time.time()
                    results.append(post_data)
                    processed_ids.add(post_data.post_id)
                    processed_count += 1
                    
                    # Save to database
                    if self.config.save_to_database and self.db:
                        self._save_to_database(post_data)
                    
                    # Add delay between posts
                    self._wait_random(
                        self.config.min_delay_seconds * 2,
                        self.config.max_delay_seconds * 2
                    )
                else:
                    self.logger.info("Skipping duplicate or invalid post")
                        
        except Exception as e:
            self.logger.error(f"Error processing page {page_name}: {str(e)}")
            
        return results
    
    def _load_initial_posts(self) -> List[WebElement]:
        """
        Load initial posts from the current page.
        
        Returns:
            List of WebElement objects representing posts
        """
        posts = []
        
        # Initial scroll to trigger post loading
        self.browser.scroll(times=1, default_key=Keys.PAGE_DOWN)
        self._wait_random(3, 5)
        
        # Try to load posts with retries
        for attempt in range(self.max_initial_post_attempts):
            posts = self.scraper.select_posts()
            
            if len(posts) >= self.min_posts_required:
                self.logger.info(f"Found {len(posts)} posts on attempt {attempt + 1}")
                break
                
            self.logger.info(f"No posts found on attempt {attempt + 1}; scrolling")
            self.scraper.scroll_page(times=2)
            self._wait_random(
                self.config.min_delay_seconds,
                self.config.max_delay_seconds
            )
        else:
            self.logger.warning(f"No posts loaded after {self.max_initial_post_attempts} attempts")
            
        return posts
    
    def _process_single_post(
        self,
        post_element: WebElement,
        page_name: str,
        comment_on_post: bool
    ) -> Optional[PostData]:
        """
        Process a single Facebook post.
        
        Args:
            post_element: WebElement of the post
            page_name: Name of the Facebook page
            comment_on_post: Whether to comment on this post
            
        Returns:
            PostData object with extracted information, or None if failed
        """
        post_data = PostData(page_name=page_name)
        
        try:
            # Extract post ID
            post_data.post_id = self._extract_post_id(post_element)
            if not post_data.post_id:
                self.logger.warning("Failed to extract post ID")
                return None
            else:
                if self.db and self.db.post_exists(post_data.post_id):
                    self.logger.info(f"Post {post_data.post_id} already processed; skipping")
                    return None
                            
            # Open post in new tab
            if not self._open_post_in_new_tab(page_name, post_data.post_id):
                self.logger.warning("Failed to open post in new tab")
                return None
            
            # Extract post content
            post_data.post_text, post_data.article_url = self._extract_post_content()
            
            # Process article if URL found
            if post_data.article_url:
                post_data.article_text = self._scrape_article(post_data.article_url)
                
                if post_data.article_text and post_data.post_text:
                    post_data.analysis = self._analyze_content(
                        post_data.post_text,
                        post_data.article_text
                    )
                    
                    # Post comment if enabled and analysis successful
                    if comment_on_post and post_data.analysis and post_data.analysis.get('output'):
                        self._post_comment(post_data.analysis['output'])
            
            # Close post tab
            self.browser.close_current_tab()
            
        except Exception as e:
            self.logger.error(f"Error processing post: {str(e)}")
            # Ensure we're back on the main page
            try:
                self.browser.close_all_other_tabs()
            except:
                pass
                
        return post_data
    
    def _extract_post_id(self, post_element: WebElement) -> Optional[str]:
        """
        Extract the post ID from a post element.
        
        Args:
            post_element: WebElement of the post
            
        Returns:
            Post ID string or None if extraction failed
        """
        try:
            # Scroll to post and make it visible
            self.browser.scroll_to_element(post_element)
            
            # Find the link element that contains post ID
            link_element = post_element.find_element(
                By.CSS_SELECTOR, 
                self.scraper.CSS_SELECTOR_POST_ID_ELEMENT
            )
            
            # Hover to reveal the actual post link
            self.browser.scroll_to_element(link_element)
            self.browser.scroll(times=3)
            self.browser.hover_element(link_element)
            self._wait_random(0.5, 1.5)
            
            # Extract the post link
            post_link_element = post_element.find_element(
                By.CSS_SELECTOR,
                self.scraper.CSS_SELECTOR_POST_ID_ON_HOVER
            )
            post_link = post_link_element.get_attribute("href")
            
            # Extract ID from URL
            post_id = self.scraper.url_utils.extract_post_id(post_link)
            
            if post_id:
                self.logger.info(f"Extracted post ID: {post_id}")
            
            return post_id
            
        except Exception as e:
            self.logger.error(f"Failed to extract post ID: {str(e)}")
            return None
    
    def _open_post_in_new_tab(self, page_name: str, post_id: str) -> bool:
        """
        Open a post in a new tab.
        
        Args:
            page_name: Name of the Facebook page
            post_id: ID of the post
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Opening post {post_id} in new tab...")
            if self.scraper.open_post_in_new_tab(page_name, post_id):
                post_url = f"{Config.SOURCE_URL}{page_name}/posts/{post_id}"
                self.logger.info(f"Opened post URL: {post_url}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to open post in new tab: {str(e)}")
            return False
    
    def _extract_post_content(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract text and article URL from the current post.
        
        Returns:
            Tuple of (post_text, article_url)
        """
        post_text = None
        article_url = None
        
        try:
            # Wait for dialog to load
            self._wait_random(2, 3)
            
            # Find the post dialog box
            post_box = self.browser.find_element(
                By.CSS_SELECTOR,
                'div[aria-labelledby][role="dialog"]'
            )
            
            # Extract post text
            post_text = self._extract_post_text(post_box)
            
            # Extract article URL using multiple strategies
            article_url = self._extract_article_url(post_box, post_text)
            
        except Exception as e:
            self.logger.error(f"Failed to extract post content: {str(e)}")
            
        return post_text, article_url
    
    def _extract_post_text(self, post_box: WebElement) -> Optional[str]:
        """
        Extract text content from a post.
        
        Args:
            post_box: WebElement of the post dialog
            
        Returns:
            Extracted text or None
        """
        try:
            text_boxes = post_box.find_elements(
                By.CSS_SELECTOR,
                "div[data-ad-comet-preview='message']"
            )
            
            # Use overlay box if multiple elements found
            if len(text_boxes) > 1:
                self.logger.debug("Multiple root elements found, using overlay box")
                text_box = text_boxes[1]
            elif text_boxes:
                text_box = text_boxes[0]
            else:
                self.logger.warning("No text box found")
                return None
            
            # Extract text from divs
            text_divs = text_box.find_elements(
                By.CSS_SELECTOR,
                "div.html-div > div > div[dir='auto']"
            )
            
            post_texts = "\n".join([
                d.text.strip() for d in text_divs if d.text.strip()
            ])
            
            self.logger.info(f"Extracted post text: {post_texts[:100]}...")
            return post_texts
            
        except Exception as e:
            self.logger.error(f"Failed to extract post text: {str(e)}")
            return None
    
    def _extract_article_url(
        self, 
        post_box: WebElement,
        post_text: Optional[str]
    ) -> Optional[str]:
        """
        Extract article URL using multiple strategies.
        
        Args:
            post_box: WebElement of the post dialog
            post_text: Previously extracted post text
            
        Returns:
            Article URL or None
        """
        strategies = [
            (PostExtractionStrategy.POST_CARD, self._extract_url_from_card),
            (PostExtractionStrategy.POST_TEXT, self._extract_url_from_text),
            (PostExtractionStrategy.COMMENT_SECTION, self._extract_url_from_comments)
        ]
        
        for strategy, method in strategies:
            try:
                self.logger.info(f"Trying {strategy.value} extraction...")
                url = method(post_box, post_text)
                if url:
                    self.logger.info(f"Found URL via {strategy.value}: {url}")
                    return url
            except Exception as e:
                self.logger.debug(f"{strategy.value} extraction failed: {str(e)}")
                
        self.logger.warning("No article URL found with any strategy")
        return None
    
    def _extract_url_from_card(
        self,
        post_box: WebElement,
        post_text: Optional[str]
    ) -> Optional[str]:
        """Extract URL from post card with image."""
        article_link = post_box.find_element(
            By.CSS_SELECTOR,
            'a[aria-label][attributionsrc][href][tabindex="0"][role="link"][target="_blank"]'
        )
        
        # Trigger hover to get full URL
        self.browser.driver.execute_script(
            """
            var ev = new MouseEvent('mouseover', {bubbles:true, cancelable:true, view: window});
            arguments[0].dispatchEvent(ev);
            """,
            article_link
        )
        self.browser.hover_element(article_link)
        self._wait_random(1.5, 2.5)
        
        return article_link.get_attribute("href")
    
    def _extract_url_from_text(
        self,
        post_box: WebElement,
        post_text: Optional[str]
    ) -> Optional[str]:
        """Extract URL from post text content."""
        if post_text:
            return self.scraper.url_utils.extract_url(post_text)
        return None
    
    def _extract_url_from_comments(
        self,
        post_box: WebElement,
        post_text: Optional[str]
    ) -> Optional[str]:
        """Extract URL from comment section."""
        article_links = post_box.find_elements(
            By.CSS_SELECTOR,
            "a[attributionsrc][rel='nofollow noreferrer'][role='link'][tabindex='0'][target='_blank']"
        )
        
        # Filter out links with aria attributes
        filtered_links = [
            link for link in article_links
            if link.get_attribute("aria-labelledby") is None
            and link.get_attribute("aria-label") is None
        ]
        
        # Return first valid link
        for link in filtered_links:
            href = link.get_attribute("href")
            text = link.text.strip()
            if href and text:
                return href
                
        return None
    
    def _scrape_article(self, article_url: str) -> Optional[str]:
        """
        Scrape article content from URL.
        
        Args:
            article_url: URL of the article
            
        Returns:
            Article text or None
        """
        try:
            self.logger.info(f"Scraping article: {article_url}")
            self.browser.open_new_tab(article_url)
            self._wait_random(2, 3)
            
            article_text = self.article_scraper.scrape_article(
                self.browser.driver.current_url
            )
            
            # Close article tab
            self.browser.close_current_tab()
            
            if article_text:
                self.logger.info(f"Scraped article text: {len(article_text)} characters")
            
            return article_text
            
        except Exception as e:
            self.logger.error(f"Failed to scrape article: {str(e)}")
            try:
                self.browser.close_current_tab()
            except:
                pass
            return None
    
    def _analyze_content(
        self,
        post_text: str,
        article_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze post and article content.
        
        Args:
            post_text: Facebook post text
            article_text: Article content
            
        Returns:
            Analysis results dictionary or None
        """
        try:
            self.logger.info("Analyzing content...")
            analysis = self.analyzer.analyze(post_text, article_text)
            
            if analysis and analysis.get('output'):
                self.logger.info(f"Analysis complete: {analysis['output'][:100]}...")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            return None
    
    def _post_comment(self, comment_text: str) -> bool:
        """
        Post a comment on the current post.
        
        Args:
            comment_text: Text to post as comment
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Posting comment...")
            
            # Find post dialog and comment box
            post_box = self.browser.find_element(
                By.CSS_SELECTOR,
                'div[aria-labelledby][role="dialog"]'
            )
            
            comment_box = post_box.find_element(
                By.CSS_SELECTOR,
                self.poster.CSS_SELECTOR_COMMENT_BOX
            )
            
            # Scroll to comment box and activate it
            self.browser.scroll_to_element(comment_box)
            self._wait_random(0.5, 1.5)
            
            comment_box.click()
            self._wait_random(0.5, 1.5)
            
            # Type comment with human-like delay
            self.browser.type_with_delay(comment_box, comment_text)
            
            self.logger.info("Comment posted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to post comment: {str(e)}")
            return False
    
    def _save_to_database(self, post_data: PostData) -> None:
        """
        Save post data to database.
        
        Args:
            post_data: PostData object to save
        """
        try:
            if self.db:
                self.logger.info(f"Saving post {post_data.post_id} to database")
                # Implementation depends on database schema
                # self.db.save_post(post_data)
        except Exception as e:
            self.logger.error(f"Failed to save to database: {str(e)}")
    
    def _wait_random(self, min_seconds: float, max_seconds: float) -> None:
        """
        Wait for a random time between min and max seconds.
        
        Args:
            min_seconds: Minimum wait time
            max_seconds: Maximum wait time
        """
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def close(self) -> None:
        """Clean up resources and close browser."""
        try:
            self.browser.close()
        except Exception as e:
            self.logger.error(f"Error closing browser: {str(e)}")