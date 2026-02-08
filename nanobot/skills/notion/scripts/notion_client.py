"""
Notion API Helper Script
Provides functions for interacting with Notion databases and pages.
"""

import json
import os
import requests
from typing import Dict, List, Optional, Any


class NotionClient:
    """Client for interacting with Notion API."""

    API_VERSION = "2022-06-28"
    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Notion client.

        Args:
            api_key: Notion API key. If None, reads from config.json
        """
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._load_api_key_from_config()

    def _load_api_key_from_config(self) -> str:
        """Load API key from ~/.nanobot/config.json file."""
        # Use nanobot's standard config location
        config_path = os.path.expanduser('~/.nanobot/config.json')

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                "~/.nanobot/config.json not found. Please create it with your Notion API key.\n"
                "Add to your config: {'tools': {'notion': {'apiKey': 'secret_YOUR_KEY'}}}"
            )

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Check for Notion API key in the tools section (nanobot convention)
        if 'tools' in config and 'notion' in config['tools'] and 'apiKey' in config['tools']['notion']:
            return config['tools']['notion']['apiKey']

        # Fallback to old structure for backward compatibility
        if 'notion' in config and 'api_key' in config['notion']:
            return config['notion']['api_key']

        raise ValueError(
            "Notion API key not found in ~/.nanobot/config.json.\n"
            "Please add: {'tools': {'notion': {'apiKey': 'secret_YOUR_KEY'}}}"
        )

    def _make_request(
            self,
            endpoint: str,
            method: str = 'GET',
            data: Optional[Dict] = None
    ) -> Dict:
        """
        Make a request to Notion API.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method (GET, POST, PATCH)
            data: Request payload

        Returns:
            JSON response from API

        Raises:
            Exception: On API errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data or {})
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, json=data or {})
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_msg = self._parse_error(response)
            raise Exception(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}") from e

    def _parse_error(self, response: requests.Response) -> str:
        """Parse error message from Notion API response."""
        if response.status_code == 401:
            return "Authentication failed. Check your Notion API key in config.json"
        elif response.status_code == 404:
            return "Resource not found. Make sure the database/page is shared with your Notion integration."
        elif response.status_code == 400:
            try:
                error_data = response.json()
                return f"Validation error: {error_data.get('message', 'Invalid request')}"
            except:
                return "Invalid request. Check your data format."
        elif response.status_code == 429:
            return "Rate limit exceeded. Please wait before retrying."
        else:
            return f"Notion API error ({response.status_code}): {response.text}"

    def list_databases(self) -> List[Dict]:
        """
        List all databases accessible to the integration.

        Returns:
            List of database objects with id, title, and url
        """
        results = self._search_with_pagination(filter_type="database")

        databases = []
        for db in results:
            title = self._extract_title(db.get('title', []))
            databases.append({
                'id': db['id'],
                'title': title or 'Untitled Database',
                'url': db['url']
            })

        return databases

    def _search_with_pagination(self, filter_type: Optional[str] = None) -> List[Dict]:
        """Search with automatic pagination handling."""
        all_results = []
        has_more = True
        start_cursor = None

        while has_more:
            payload = {}
            if start_cursor:
                payload['start_cursor'] = start_cursor
            if filter_type:
                payload['filter'] = {
                    'property': 'object',
                    'value': filter_type
                }

            response = self._make_request('search', 'POST', payload)
            all_results.extend(response.get('results', []))

            has_more = response.get('has_more', False)
            start_cursor = response.get('next_cursor')

        return all_results

    def query_database(
            self,
            database_id: str,
            filter_conditions: Optional[Dict] = None,
            sorts: Optional[List[Dict]] = None,
            page_size: int = 100
    ) -> List[Dict]:
        """
        Query a database with filters and sorting.

        Args:
            database_id: The database ID
            filter_conditions: Filter object (see Notion API docs)
            sorts: List of sort objects
            page_size: Number of results per page (max 100)

        Returns:
            List of page objects
        """
        all_results = []
        has_more = True
        start_cursor = None

        while has_more:
            payload = {'page_size': min(page_size, 100)}

            if start_cursor:
                payload['start_cursor'] = start_cursor
            if filter_conditions:
                payload['filter'] = filter_conditions
            if sorts:
                payload['sorts'] = sorts

            response = self._make_request(
                f'databases/{database_id}/query',
                'POST',
                payload
            )

            all_results.extend(response.get('results', []))

            has_more = response.get('has_more', False)
            start_cursor = response.get('next_cursor')

        return all_results

    def create_page(
            self,
            database_id: str,
            properties: Dict[str, Any]
    ) -> Dict:
        """
        Create a new page in a database.

        Args:
            database_id: The parent database ID
            properties: Page properties matching database schema

        Returns:
            Created page object

        Example:
            properties = {
                'Name': {
                    'title': [{'text': {'content': 'Task name'}}]
                },
                'Status': {
                    'select': {'name': 'To Do'}
                }
            }
        """
        payload = {
            'parent': {'database_id': database_id},
            'properties': properties
        }

        return self._make_request('pages', 'POST', payload)

    def update_page(
            self,
            page_id: str,
            properties: Dict[str, Any]
    ) -> Dict:
        """
        Update properties of an existing page.

        Args:
            page_id: The page ID to update
            properties: Properties to update

        Returns:
            Updated page object
        """
        payload = {'properties': properties}
        return self._make_request(f'pages/{page_id}', 'PATCH', payload)

    def get_page(self, page_id: str) -> Dict:
        """Get a page by ID."""
        return self._make_request(f'pages/{page_id}', 'GET')

    def get_database(self, database_id: str) -> Dict:
        """Get database schema and metadata."""
        return self._make_request(f'databases/{database_id}', 'GET')

    @staticmethod
    def _extract_title(title_array: List[Dict]) -> str:
        """Extract plain text from Notion title array."""
        if not title_array:
            return ""
        return "".join([item.get('plain_text', '') for item in title_array])

    @staticmethod
    def build_title_property(text: str) -> Dict:
        """Build a title property for Notion."""
        return {
            'title': [
                {
                    'text': {
                        'content': text
                    }
                }
            ]
        }

    @staticmethod
    def build_rich_text_property(text: str) -> Dict:
        """Build a rich text property for Notion."""
        return {
            'rich_text': [
                {
                    'text': {
                        'content': text
                    }
                }
            ]
        }

    @staticmethod
    def build_select_property(option: str) -> Dict:
        """Build a select property for Notion."""
        return {'select': {'name': option}}

    @staticmethod
    def build_date_property(date_string: str) -> Dict:
        """Build a date property for Notion (format: YYYY-MM-DD)."""
        return {'date': {'start': date_string}}

    @staticmethod
    def build_checkbox_property(checked: bool) -> Dict:
        """Build a checkbox property for Notion."""
        return {'checkbox': checked}


# Helper functions for common operations

def list_all_databases() -> List[Dict]:
    """List all databases - convenience function."""
    client = NotionClient()
    return client.list_databases()


def find_database_by_name(name: str) -> Optional[Dict]:
    """Find a database by name (case-insensitive)."""
    client = NotionClient()
    databases = client.list_databases()

    name_lower = name.lower()
    for db in databases:
        if name_lower in db['title'].lower():
            return db

    return None


def create_simple_task(database_id: str, title: str, status: str = 'To Do') -> Dict:
    """
    Create a simple task with title and status.

    Args:
        database_id: Database ID to create task in
        title: Task title
        status: Task status (default: 'To Do')

    Returns:
        Created page object
    """
    client = NotionClient()

    properties = {
        'Name': client.build_title_property(title),
        'Status': client.build_select_property(status)
    }

    return client.create_page(database_id, properties)


# Example usage
if __name__ == '__main__':
    # Example: List all databases
    print("Listing all databases...")
    try:
        client = NotionClient()
        databases = client.list_databases()

        print(f"\nFound {len(databases)} database(s):\n")
        for i, db in enumerate(databases, 1):
            print(f"{i}. {db['title']}")
            print(f"   ID: {db['id']}")
            print(f"   URL: {db['url']}\n")

    except Exception as e:
        print(f"Error: {e}")