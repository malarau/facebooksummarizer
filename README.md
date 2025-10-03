# Facebook Automation & Analysis Bot 🤖

This project provides an automated workflow for interacting with Facebook pages. It scrapes recent posts, follows links to external articles, analyzes the content using Large Language Models (LLMs) via [OpenRouter.ai](https://openrouter.ai), and can post intelligent, context-aware comments (anti-clickbait).

The primary goal is to demonstrate a full-cycle automation pipeline, from data extraction and web interaction to AI-powered content analysis and generation.

---

## ✨ Features

- **Automated Facebook Login**: Securely logs into a Facebook account to perform actions.
- **Multi-Page Scraping**: Monitors and scrapes posts from a configurable list of Facebook pages.
- **AI-Powered Content Analysis**: Integrates with OpenRouter.ai to perform tasks like:
  - Clickbait detection.
  - Article summarization.
  - Generating insightful comments.
- **Human-Like Interactions**: Simulates human behavior with randomized delays and typing patterns to reduce the risk of detection.
- **Flexible Execution Modes**:
  - `single`: Runs the workflow once and exits.
  - `scheduled`: Runs continuously at a defined interval.
- **Docker Support**: Comes ready for containerization with Docker, allowing for isolated and reproducible environments.
- **Headless Operation**: Can run the browser in the background (headless mode) for server-based deployments.

---

## 📄 Prompt Configuration

The prompts that control how the AI analyzes texts are stored in the `prompts.json` file. You can edit this file to customize the AI's behavior without modifying the code.

### Format of `prompts.json`

The file contains two fields:

- `system_prompt`: Defines general instructions for the AI.
- `user_prompt`: Specifies the format for input data, using `{post_text}` and `{article_text}` as placeholders.

---

## ⚙️ How It Works

The workflow is orchestrated by the main `app_runner.py` script and follows these steps:

1. **Initialize & Login**: The browser driver (Selenium) starts and logs into the Facebook account specified in the `.env` file.
2. **Navigate to Target Page**: The bot navigates to the first Facebook page in your list.
3. **Scrape Posts**: It scrolls the page to load and identify recent posts based on predefined CSS selectors.
4. **Process Each Post**: For each post found, the bot:
   - Extracts a unique post ID.
   - Opens the post in a new browser tab to isolate the view.
   - Finds and extracts the URL of an external article linked in the post.
   - Opens the article in another tab and scrapes its full text content.
   - Sends the post's text and the article's text to the OpenRouter API.
   - Receives an analysis (e.g., summary, clickbait score) and a generated comment.
5. **Post Comment (Optional)**: If `ENABLE_COMMENTS` is true, the bot types the AI-generated comment and posts it.
6. **Loop & Repeat**: The bot adds a delay, then moves to the next post or the next page in the list.
7. **Schedule Next Run**: In `scheduled` mode, the bot waits for the configured interval before running the entire workflow again.

---

## ✅ Prerequisites

Before you begin, ensure you have the following:

- **Python 3.8+**
- **A Facebook Account**: ⚠️ It is strongly recommended to use a secondary or "burner" account. Automated activity can lead to account restrictions or bans.
- **An OpenRouter API Key**:
  1. Sign up at [https://openrouter.ai/](https://openrouter.ai/).
  2. Create an account.
  3. Go to your Account Settings and create a new API Key.

---

## 🚀 Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/malarau/facebooksummarizer.git
cd facebooksummarizer
```

### 2. Configure Your Environment

The project is configured using a `.env` file. Create one by copying the example file `.env.example`.
Now, open the `.env` file and fill in your details. See the section below for a detailed explanation of each variable.

---

## 🔑 Environment Variables (`.env` file)

This file stores all your credentials and configuration settings. **Never commit this file to version control.**

| Variable                   | Description                                                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `FB_EMAIL` / `FB_PASSWORD` | Your Facebook login credentials. Again, use a test (fake) account.                                                                    |
| `FACEBOOK_PAGES`           | A comma-separated list of the Facebook page slugs (the part after `facebook.com/`).                                                   |
| `OPENROUTER_API_KEY`       | Your secret API key from OpenRouter.ai.                                                                                               |
| `OPENROUTER_MODEL`         | The LLM you want to use for analysis. You can find (free) model names on the OpenRouter site.                                         |
| `MAX_POSTS_PER_PAGE`       | Limits how many of the latest posts the bot will process on each page during a single run.                                            |
| `ENABLE_COMMENTS`          | Master switch to enable (`true`) or disable (`false`) the comment-posting feature.                                                    |
| `RUN_MODE`                 | Determines if the app runs once (`single`) or continuously (`scheduled`).                                                             |
| `DAILY_..._LIMIT`          | Safety limits to stop the bot after processing/commenting a certain number of times in a day.                                         |
| `HEADLESS_MODE`            | Set to `true` for server environments where you don't have a display. Set to `false` during development to see what the bot is doing. |
| `DOCKER_ENV`               | Critical for Docker. Set to `true` to make the app connect to the Selenium container at `http://selenium:4444/wd/hub`.                |
| `LOG_LEVEL`                | Controls the verbosity of the console logs. Use `DEBUG` for detailed troubleshooting.                                                 |

---

## ▶️ How to Run

You can run this project locally on your machine or using Docker for a more stable and isolated environment.

### 🖥 Local Execution

#### 1. Ensure your `.env` file is complete.
#### 2. Create and Activate a Virtual Environment

It uses `venv` to keep project dependencies isolated.

```bash
# Create the virtual environment
python -m venv .venv

# Activate it:
  # On macOS and Linux:
source .venv/bin/activate

  # On Windows:
.\.venv\Scripts\activate
```

#### 3. Install Dependencies

Install all the required Python packages from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

#### 4. Make sure your Python virtual environment (`.venv`) is activated and run the main application script from your terminal:

```bash
python app_runner.py
```

A Chrome browser window will open on your desktop, and the automation will begin. You can monitor the progress in the terminal.

---

### 🐳 Docker Execution (Development/Testing)

This method uses Docker Compose to run the application and a dedicated Selenium browser in separate, linked containers, using the `docker-compose.dev.yml` file. This approach is highly recommended as it avoids local browser and driver version conflicts.

#### 1. Prerequisites

* Ensure you have Docker and Docker Compose installed.
* Make sure your local `.env` file is complete.

#### 2. Build and Run the Containers

From your project's root directory, run the following command to build the application image and start the services in detached mode (in the background):

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

#### 3. Monitor the Application

You can view the logs of the application container to see its progress:

```bash
docker compose logs -f app
```

(Press `Ctrl + C` to stop viewing the logs.)

#### 4. 👀 View the Live Browser Session (No 3rd Party Software Needed)

Since you are running with `HEADLESS_MODE=false`, you can watch the bot in real-time:

Open your web browser and navigate to:

```
http://localhost:7900
```

The Selenium VNC server will provide a live, interactive view of the browser inside the container.