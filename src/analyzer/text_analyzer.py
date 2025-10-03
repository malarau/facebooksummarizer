import requests, json, os
from src.config.config import Config
from typing import Dict

class TextAnalyzer:
    """Analyzes text using OpenRouter.ai models."""
    def __init__(self, prompt_file: str = os.path.join("prompts.json")):
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.OPENROUTER_MODEL
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Load prompts from JSON file
        try:
            with open(prompt_file, 'r', encoding='utf-8') as file:
                prompts = json.load(file)
                self.system_prompt = prompts["system_prompt"]
                self.user_prompt = prompts["user_prompt"]
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {prompt_file} was not found.")
        except KeyError as e:
            raise KeyError(f"Missing key {e} in {prompt_file}. Ensure it contains 'system_prompt' and 'user_prompt'.")
        except json.JSONDecodeError:
            raise ValueError(f"The file {prompt_file} is not a valid JSON.")

    def analyze(self, post_text: str, article_text: str) -> Dict:
        """Analyzes a Facebook post and related article text."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_prompt.format(post_text=post_text, article_text=article_text)}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        return {
            "output": result["choices"][0]["message"]["content"].strip()
        }