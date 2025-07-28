"""
Configuration management for YouTrack client.
Handles environment variables and user input.
"""

import os
from pathlib import Path
from typing import Optional

import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


class ConfigManager:
    """Manages configuration for YouTrack client."""
    base_url: Optional[str] = None
    token: Optional[str] = None

    def __init__(self, env_file: str = '.env'):
        """
        Initialize the Configuration Manager.
        Args:
            env_file (str): Path to the .env file to store credentials (!! should be a file that is also in the gitignore !!).
        """
        self.env_file = Path(env_file)
        self._load_env_file()

    def _load_env_file(self):
        """Load environment variables from .env file."""
        if self.env_file.exists():
            console.print('Loading environment configuration...', style='dim')
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
        console.print(f'Credentials saved to {self.env_file} \n', style='green')

    def get_youtrack_url(self) -> Optional[str]:
        """
        Get YouTrack URL from environment or prompt user.
        Returns:
            Optional[str]: YouTrack URL.
        """
        self.base_url = os.getenv('YOUTRACK_URL')
        if not self.base_url:
            self.base_url = self._prompt_for_url()
            if self.base_url:
                self._save_credentials()
        return self.base_url

    def get_youtrack_token(self) -> Optional[str]:
        """
        Get YouTrack token from environment or prompt user.
        Returns:
            Optional[str]: YouTrack token
        """
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
    def _prompt_for_url() -> str:
        """
        Prompt user for their YouTrack instance URL.
        Returns:
            str: YouTrack instance URL.
        """

        console.print(Markdown('## YouTrack Configuration'), style='bold #8265FA')

        url = questionary.text(
            'Enter your YouTrack URL:',
            qmark='🌐',
            instruction='(e.g., https://youtrack.example.com)',
            validate=lambda text: True if text.strip() else "URL to your YouTrack instance is required!"
        ).ask()

        if url is None:
            raise KeyboardInterrupt

        # Parse the URL format
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        return url.strip('/')

    @staticmethod
    def _prompt_for_token() -> str:
        """
        Prompt user for YouTrack API token.
        Returns:
            str: YouTrack API token.
        """

        panel_md = '''**How you can find your API token in YouTrack:**\n
- Go to Settings > Personal > Tokens\n 
- Create a new token with appropriate permissions\n 
- Copy the token and paste it below\n'''
        console.print(Panel(Markdown(panel_md), title='YouTrack API Token', style='blue', width=100))

        token = questionary.password(
            'Enter your YouTrack API token:',
            qmark='🔑',
            validate=lambda text: True if text.strip() else "API token is required!"
        ).ask()

        if token is None:
            raise KeyboardInterrupt

        return token
