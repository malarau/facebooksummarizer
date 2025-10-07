"""
Facebook Automation App Runner

Main application runner with scheduling capabilities for continuous Facebook automation.
Supports both single-run and scheduled execution modes with configurable intervals.
"""
import os
import sys
import time
import signal
import logging
import schedule
from datetime import datetime
from typing import Optional, List
from threading import Event
from dotenv import load_dotenv

from src.browser.facebook_automation_workflow import (
    FacebookAutomationWorkflow,
    FacebookConfig,
    PostData
)
from src.utils.logger import app_logger

# Load environment variables
load_dotenv()


class FacebookAutomationApp:
    """
    Main application class for Facebook automation.
    
    Handles:
    - Scheduled execution of automation workflow
    - Statistics tracking
    - Graceful shutdown
    - Error recovery and retries
    """
    
    def __init__(self):
        """Initialize the Facebook automation application."""
        self.logger = app_logger or logging.getLogger(__name__)
        self.config = FacebookConfig()
        self.workflow: Optional[FacebookAutomationWorkflow] = None
        
        # Execution settings from environment
        self.run_mode = os.getenv('RUN_MODE', 'scheduled')  # 'single' or 'scheduled'
        self.run_interval_minutes = int(os.getenv('RUN_INTERVAL_MINUTES', '60'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay_seconds = int(os.getenv('RETRY_DELAY_SECONDS', '300'))
        
        # Daily limits from environment
        self.daily_post_limit = int(os.getenv('DAILY_POST_LIMIT', '100'))
        self.daily_comment_limit = int(os.getenv('DAILY_COMMENT_LIMIT', '50'))
        
        # Statistics tracking
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'total_posts_processed': 0,
            'total_comments_posted': 0,
            'total_articles_analyzed': 0,
            'daily_posts_processed': 0,
            'daily_comments_posted': 0,
            'last_run_time': None,
            'next_run_time': None,
            'errors': []
        }
        
        # Control flags
        self.shutdown_event = Event()
        self.is_running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.shutdown_event.set()
        
    def start(self):
        """Start the Facebook automation application."""
        self.logger.info("=" * 60)
        self.logger.info("Facebook Automation App Starting")
        self.logger.info(f"Run Mode: {self.run_mode}")
        self.logger.info(f"Pages to monitor: {', '.join(self.config.facebook_pages)}")
        self.logger.info(f"Max posts per page: {self.config.max_posts_per_page}")
        self.logger.info(f"Comments enabled: {self.config.enable_comments}")
        
        if self.run_mode == 'single':
            self.logger.info("Running single execution...")
            self._run_single()
        else:
            self.logger.info(f"Running scheduled execution every {self.run_interval_minutes} minutes")
            self._run_scheduled()
            
    def _run_single(self):
        """Execute a single run of the workflow."""
        try:
            self._execute_workflow_with_retries()
        except Exception as e:
            self.logger.error(f"Single run failed after all retries: {str(e)}")
            sys.exit(1)
        finally:
            self.logger.info("Single run finished.")
            self._print_statistics()

    def _run_scheduled(self):
        """Run the workflow on a schedule."""
        # Schedule the job
        schedule.every(self.run_interval_minutes).minutes.do(self._execute_workflow_with_retries)
        self.logger.info("Initial job scheduled. First run will start shortly.")
        
        # Run the first job immediately
        self._execute_workflow_with_retries()
        
        while not self.shutdown_event.is_set():
            next_run = schedule.next_run() 
            
            if next_run:
                self.stats['next_run_time'] = next_run.strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.stats['next_run_time'] = None
            
            schedule.run_pending()
            time.sleep(1)
        
        self.logger.info("Shutdown signal received. Exiting scheduled loop.")
        self.stop()

        
    def _execute_workflow_with_retries(self):
        """Execute the workflow with a retry mechanism."""
        for attempt in range(self.max_retries):

            if self.shutdown_event.is_set():
                self.logger.info("Shutdown event set. Exiting orkflow with retries loop.")
                return

            try:
                self._execute_workflow()
                return  # Success, exit retry loop
            except Exception as e:
                self.logger.error(f"Workflow execution failed on attempt {attempt + 1}/{self.max_retries}. Error: {str(e)}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay_seconds} seconds...")
                    time.sleep(self.retry_delay_seconds)
                else:
                    self.logger.error("All retries failed. The workflow will not be executed this cycle.")
                    raise

    def _execute_workflow(self):
        """Core logic to run the automation workflow, wrapped with error handling and statistics."""
        if self.is_running:
            self.logger.warning("Workflow is already running. Skipping this scheduled execution.")
            return

        self.is_running = True
        self.stats['total_runs'] += 1
        self.stats['last_run_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info(f"Starting workflow run #{self.stats['total_runs']}...")
        
        try:
            self._reset_daily_stats_if_needed()

            # Check daily limits before starting
            if self.stats['daily_posts_processed'] >= self.daily_post_limit:
                self.logger.warning(f"Daily post limit of {self.daily_post_limit} reached. Skipping run.")
                return
            if self.config.enable_comments and self.stats['daily_comments_posted'] >= self.daily_comment_limit:
                self.logger.warning(f"Daily comment limit of {self.daily_comment_limit} reached. Skipping run.")
                return

            self.workflow = FacebookAutomationWorkflow(self.config, self.shutdown_event)
            results = self.workflow.run_workflow()
            self._update_statistics(results)
            self.stats['successful_runs'] += 1
            self.logger.info(f"Workflow run #{self.stats['total_runs']} completed successfully.")

        except Exception as e:
            self.stats['failed_runs'] += 1
            error_msg = f"An unhandled exception occurred during workflow execution: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.stats['errors'].append(f"{self.stats['last_run_time']}: {error_msg}")
            raise  # Re-raise the exception to be caught by the retry handler

        finally:
            if self.workflow:
                self.workflow.close()
                self.workflow = None
            self.is_running = False
            self.logger.info("Workflow run finished.")
            self._print_statistics()
    
    def _update_statistics(self, results: List[PostData]):
        """Update run statistics based on workflow results."""
        posts_processed_this_run = len(results)
        self.stats['total_posts_processed'] += posts_processed_this_run
        self.stats['daily_posts_processed'] += posts_processed_this_run
        
        comments_posted_this_run = 0
        articles_analyzed_this_run = 0
        
        for post in results:
            if post.article_text:
                articles_analyzed_this_run += 1
            # Assuming a comment is posted if analysis output exists and comments are enabled
            if self.config.enable_comments and post.analysis and post.analysis.get('output'):
                comments_posted_this_run += 1

        self.stats['total_articles_analyzed'] += articles_analyzed_this_run
        self.stats['total_comments_posted'] += comments_posted_this_run
        self.stats['daily_comments_posted'] += comments_posted_this_run
        
        self.logger.info(f"Run summary: Processed {posts_processed_this_run} posts, analyzed {articles_analyzed_this_run} articles, posted {comments_posted_this_run} comments.")

    def _reset_daily_stats_if_needed(self):
        """Resets daily counters if a new day has started."""
        now = datetime.now()
        last_run_str = self.stats.get('last_run_time')
        if last_run_str:
            last_run_time = datetime.strptime(last_run_str, '%Y-%m-%d %H:%M:%S')
            if last_run_time.date() < now.date():
                self.logger.info("New day detected. Resetting daily statistics.")
                self.stats['daily_posts_processed'] = 0
                self.stats['daily_comments_posted'] = 0

    def _print_statistics(self):
        """Prints a summary of the current application statistics."""
        self.logger.info("-" * 60)
        self.logger.info("Application Statistics:")
        self.logger.info(f"  Total Runs: {self.stats['total_runs']} (Successful: {self.stats['successful_runs']}, Failed: {self.stats['failed_runs']})")
        self.logger.info(f"  Total Posts Processed: {self.stats['total_posts_processed']}")
        self.logger.info(f"  Total Comments Posted: {self.stats['total_comments_posted']}")
        self.logger.info(f"  Total Articles Analyzed: {self.stats['total_articles_analyzed']}")
        self.logger.info(f"  Daily Posts Processed: {self.stats['daily_posts_processed']}/{self.daily_post_limit}")
        self.logger.info(f"  Daily Comments Posted: {self.stats['daily_comments_posted']}/{self.daily_comment_limit}")
        self.logger.info(f"  Last Run Time: {self.stats['last_run_time'] or 'N/A'}")
        if self.run_mode == 'scheduled':
            self.logger.info(f"  Next Scheduled Run: {self.stats['next_run_time'] or 'Calculating...'}")
        self.logger.info("-" * 60)
        
    def stop(self):
        """Clean up resources and stop the application."""
        self.logger.info("Stopping the application...")
        if self.workflow:
            self.workflow.close()
        self.logger.info("Final statistics:")
        self._print_statistics()
        self.logger.info("Shutdown complete.")


if __name__ == "__main__":
    app = FacebookAutomationApp()
    app.start()