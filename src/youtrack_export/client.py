"""
YouTrack API Client
Provides convenient access to the YouTrack REST API.
"""

import requests
from typing import Optional, Dict
from .exceptions import AuthenticationError
from .config import ConfigManager


class YouTrackClient:
    """Client for interacting with YouTrack REST API."""
    __user: Optional[Dict] = None

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the YouTrack client.

        Args:
            base_url: YouTrack instance URL
            token: API token for authentication
        """
        self.config_manager = ConfigManager()

        # Get credentials from environment or prompt user
        self.base_url = base_url or self.config_manager.get_youtrack_url()
        self.token = token or self.config_manager.get_youtrack_token()

        # Validate credentials
        if not self.base_url or not self.token:
            raise AuthenticationError('YouTrack URL and token are required')

        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # Validate connection
        self._validate_connection()

    def _validate_connection(self):
        """Validate the connection to YouTrack."""
        try:
            response = self.session.get(f'{self.base_url}/api/users/me')
            response.raise_for_status()
        except requests.RequestException as e:
            raise AuthenticationError(f'Failed to connect to YouTrack: {e}')

    def get_current_user(self) -> Dict:
        """Get information about the current user."""
        if self.__user:
            return self.__user

        response = self.session.get(f'{self.base_url}/api/users/me?fields=id,login,name,email')
        response.raise_for_status()
        self.__user = response.json()
        return self.__user

    def get_projects(self) -> list:
        """Get all projects."""
        response = self.session.get(f'{self.base_url}/api/admin/projects?fields=id,name,archived&$top=100&$skip=0')
        response.raise_for_status()
        return response.json()

    def get_issues(self, project_id: str, limit: int = 100) -> list:
        """Get issues from a specific project."""
        params = {
            'query': f'project: {project_id}',
            'fields': 'id,summary,state,assignee',
            'max': limit
        }
        response = self.session.get(f'{self.base_url}/api/issues', params=params)
        response.raise_for_status()
        return response.json()

    def get_issue_attachments(self, issue_id: int) -> list:
        """Get the attachments of a specific issue."""
