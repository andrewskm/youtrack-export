"""
Configuration management for YouTrack client.
Handles environment variables and user input.
"""

import os
import questionary
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Manages configuration for YouTrack client."""
    base_url: Optional[str] = None
    token: Optional[str] = None

    def __init__(self, env_file: str = '.env'):
        self.env_file = Path(env_file)
        self._load_env_file()

    def _load_env_file(self):
        """Load environment variables from .env file."""
        if self.env_file.exists():
            print('Loading environment configuration...')
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

    def _save_env_file(self):
        """Save credentials to .env file."""
        env_content = f"""# YouTrack Configuration
YOUTRACK_URL={self.base_url}
YOUTRACK_TOKEN={self.token}
"""
        with open(self.env_file, 'w') as f:
            f.write(env_content)
        print(f'Credentials saved to {self.env_file}')

    def get_youtrack_url(self) -> Optional[str]:
        """Get YouTrack URL from environment or prompt user."""
        self.base_url = os.getenv('YOUTRACK_URL')
        if not self.base_url:
            self.base_url = self._prompt_for_url()
            if self.base_url:
               self._save_credentials()
        return self.base_url

    def get_youtrack_token(self) -> Optional[str]:
        """Get YouTrack token from environment or prompt user."""
        self.token = os.getenv('YOUTRACK_TOKEN')
        if not self.token:
            self.token = self._prompt_for_token()
            if self.token:
               self._save_credentials()
        return self.token

    def _save_credentials(self):
        """Save credentials to .env file."""

        if self.base_url and self.token:
            self._save_env_file()

    @staticmethod
    def _prompt_for_url() -> Optional[str]:
        """Prompt user for YouTrack URL."""

        print("\nYouTrack Configuration")
        print("=" * 30)
        url = questionary.text(
            "Enter your YouTrack URL (e.g., https://youtrack.example.com):",
            qmark="🌐"
        ).ask()

        if not url:
            print("URL is required!")
            return None

        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        return url.strip('/')

    @staticmethod
    def _prompt_for_token() -> Optional[str]:
        """Prompt user for YouTrack API token."""
        print('\nAPI Token')
        print('=' * 30)
        print('You can find your API token in YouTrack:')
        print('- Go to Settings > Personal > Tokens')
        print('- Create a new token with appropriate permissions')
        print('- Copy the token and paste it below')
        print()

        token = questionary.password(
            "Enter your YouTrack API token:",
            qmark="🔑"
        ).ask()

        if not token:
            print('API token is required!')
            return None

        return token
