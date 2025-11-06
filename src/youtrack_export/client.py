"""
YouTrack API Client
Provides convenient access to the YouTrack REST API.
"""
from typing import Optional, Dict

import aiohttp
import requests

from .config import ConfigManager
from .exceptions import AuthenticationError


class YouTrackClient:
    """Client for interacting with YouTrack REST API."""
    __user: Optional[Dict] = None

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the YouTrack client.

        Args:
            base_url (Optional[str]): YouTrack instance URL.
            token (Optional[str]): API token for authentication.
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
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.session.headers.update(self.headers)

        # Validate connection
        self._validate_connection()

    def _validate_connection(self) -> None:
        """Validate the connection to YouTrack."""
        try:
            response = self.session.get(f'{self.base_url}/api/users/me')
            response.raise_for_status()
        except requests.RequestException as e:
            raise AuthenticationError(f'Failed to connect to YouTrack: {e}')

    def get_current_user(self) -> Dict:
        """
        Get information about the current user.
        Returns:
            Dict: Current user information
        """
        if self.__user:
            return self.__user

        response = self.session.get(f'{self.base_url}/api/users/me?fields=id,login,name,email')
        response.raise_for_status()
        self.__user = response.json()
        return self.__user

    def get_projects(self, limit: int = 100, skip: int = 0) -> list:
        """
        Get all projects.
        Args:
            limit (int): Number of projects to return.
            skip (int): Number of projects to skip.
        Returns:
            list: List of projects.
        """
        response = self.session.get(f'{self.base_url}/api/admin/projects?fields=id,name,description,archived&$top={limit}&$skip={skip}')
        response.raise_for_status()
        return response.json()

    async def get_project_issue_count(self, client_session: aiohttp.ClientSession, project: dict[str, str], export_items: list[str]):
        """
        Get the total number of issues for a project.
        Args:
            client_session (aiohttp.ClientSession): session instance.
            project (dict[str, str]): Project dictionary with id and name.
            export_items (list[str]): List of items to export.
        Returns:
            int: Number of issues.
        """
        data = {
            'query': f'project: {project.get('name')} {self._parse_query(export_items)}',  # todo - allow custom query along with this
        }

        async with client_session.post(f'{self.base_url}/api/issuesGetter/count?fields=count', json=data, headers=self.headers) as response:
            results = await self._session_json_response(response)
            return results.get('count', None)

    async def get_issues(self, client_session: aiohttp.ClientSession, project: dict[str, str], export_items: list[str], limit: int = 100, skip: int = 0) -> list:
        """
        Get issues for a specific project.
        Args:
            client_session (aiohttp.ClientSession): session instance.
            project (dict[str, str]): Project dictionary with id and name.
            export_items (list[str]): List of items to export.
            limit (int): Number of issues to return.
            skip (int): Number of issues to skip.
        Returns:
            list: List of issues is json.
        """
        params = {
            'query': f'project: {project.get('name')} {self._parse_query(export_items)}',  # todo - allow custom query along with this
            'fields': self._parse_fields_from_export_items(export_items),
            '$skip': skip,
            '$top': limit,
        }

        async with client_session.get(f'{self.base_url}/api/issues', params=params, headers=self.headers, timeout=15) as response:
            return await self._session_json_response(response)

    def get_issue_attachment(self, attachment: dict):
        """
        Get the attachments of a specific issue.
        Args:
            attachment (dict): A issue attachment dictionary.
        Returns:
            Response content for the attachment file.
        """
        url = attachment.get('url')
        if not url.startswith('http'):
            url = self.base_url.rstrip('/') + '/' + url.lstrip('/')

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content

    @staticmethod
    async def _session_json_response(response):
        """
        Parse the client_session response.
        Args:
            response: aiohttp.ClientSession response instance.
        Returns:
            Response from YouTrack API.
        """
        if response.status == 200:
            return await response.json()
        if response.status == 400:
            json = await response.json()
            raise Exception(f'API Error: {json.get('error')}: {json.get('error_description')}')
        else:
            raise Exception(f'Failed to receive a valid API response: status {response.status}')

    @staticmethod
    def _parse_query(export_items: list[str]) -> str:
        """
        Based on the export items, create the query string.
        Args:
            export_items (list[str]): List of export items.
        Returns:
            str: Query string.
        """
        query = []

        if 'Unresolved Issues' in export_items:
            query.append('#Unresolved')
        if 'Resolved Issues' in export_items:
            query.append('#Resolved')

        return ' '.join(query)

    @staticmethod
    def _parse_fields_from_export_items(export_items: list[str]) -> str:
        """
        Set the fields that are sent based on the export items selected.
        Args:
            export_items (list[str]): List of export items.
        Returns:
            str: Comma delimited list of fields.
        """
        fields = [
            'id,idReadable,isDraft,summary,description,created,updated,resolved',
            'tags(id,name,color),reporter(email,fullName)',
            'parent(id,direction,linkType(name),issues(id,idReadable,resolved)),subtasks(id,direction,linkType(name),issues(id,idReadable,resolved))',
            'links(id,direction,linkType(name),issues(id,idReadable,resolved))',
            'customFields(id,name,value(id,name,presentation,text))'
        ]

        if 'Comments' in export_items:
            fields.append('comments(id,author(login,name),text,created,updated)')
        if 'Attachments' in export_items:
            fields.append('attachments(id,name,url,created,author(login,name))')

        return ','.join(fields)
