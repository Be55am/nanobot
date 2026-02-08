---
name: notion
description: Interact with Notion databases and pages via the Notion API. Use when the user wants to list databases, query database entries, create new pages, update existing pages, search Notion content, or manage Notion workspace data. Triggers include mentions of "Notion", "databases", "workspace", "create page", "update page", "query database", or any Notion-related operations.
version: "1.0.0"
author: nanobot-community
license: Apache-2.0
---

# Notion Integration Skill

## Overview
This skill enables comprehensive interaction with the Notion API, allowing nanobot to manage databases, pages, and content within your Notion workspace. It supports listing databases, querying entries, creating new pages, and updating existing content.

## Prerequisites

### 1. Configuration
The skill reads the API key from `~/.nanobot/config.json` (nanobot's standard config location):

```json
{
  "tools": {
    "notion": {
      "apiKey": "secret_YOUR_API_KEY_HERE"
    }
  }
}
```

## Supported Operations

### 1. List All Databases

**When to use:** User wants to see all accessible Notion databases in their workspace.

**Process:**
1. Read API key from `config.json`
2. Make POST request to `https://api.notion.com/v1/search`
3. Filter results where `object === "database"`
4. Extract database titles, IDs, and URLs
5. Present formatted list to user

**API Call:**
```python
import requests

headers = {
    "Authorization": f"Bearer {api_key}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

payload = {
    "filter": {
        "property": "object",
        "value": "database"
    }
}

response = requests.post(
    "https://api.notion.com/v1/search",
    headers=headers,
    json=payload
)
```

**Example Output:**
```
Found 3 databases:
1. Tasks Database (ID: 12345678-1234-1234-1234-123456789abc)
2. Projects (ID: 87654321-4321-4321-4321-cba987654321)
3. Notes (ID: abcdef12-3456-7890-abcd-ef1234567890)
```

---

### 2. Query/Search Database Entries

**When to use:** User wants to find specific entries in a database or search with filters.

**Process:**
1. Identify the database ID (from list or user provides name)
2. Build query filters based on user requirements
3. Make POST request to `https://api.notion.com/v1/databases/{database_id}/query`
4. Parse and format results with page titles and properties
5. Present results to user

**API Call with Filters:**
```python
payload = {
    "filter": {
        "property": "Status",
        "select": {
            "equals": "In Progress"
        }
    },
    "sorts": [
        {
            "property": "Created",
            "direction": "descending"
        }
    ]
}

response = requests.post(
    f"https://api.notion.com/v1/databases/{database_id}/query",
    headers=headers,
    json=payload
)
```

**Common Filter Examples:**
- **Text contains:** `{"property": "Name", "rich_text": {"contains": "keyword"}}`
- **Checkbox is true:** `{"property": "Done", "checkbox": {"equals": true}}`
- **Date is after:** `{"property": "Due Date", "date": {"after": "2024-01-01"}}`
- **Select equals:** `{"property": "Status", "select": {"equals": "Active"}}`

**Example Interaction:**
- User: "Show me all tasks with status 'In Progress' from my Tasks database"
- Action: Query database with status filter
- Output: List of matching pages with titles and key properties

---

### 3. Create New Pages/Entries

**When to use:** User wants to add a new entry to a database or create a standalone page.

**Process:**
1. Identify target database ID or parent page
2. Extract properties from user request (title, status, dates, etc.)
3. Build page object with properties matching database schema
4. Make POST request to `https://api.notion.com/v1/pages`
5. Confirm creation and return new page URL

**API Call:**
```python
payload = {
    "parent": {
        "database_id": database_id
    },
    "properties": {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": "New Task Title"
                    }
                }
            ]
        },
        "Status": {
            "select": {
                "name": "To Do"
            }
        },
        "Due Date": {
            "date": {
                "start": "2024-12-31"
            }
        }
    }
}

response = requests.post(
    "https://api.notion.com/v1/pages",
    headers=headers,
    json=payload
)
```

**Property Type Mappings:**
- **Title:** `{"title": [{"text": {"content": "text"}}]}`
- **Rich Text:** `{"rich_text": [{"text": {"content": "text"}}]}`
- **Number:** `{"number": 42}`
- **Select:** `{"select": {"name": "option"}}`
- **Multi-select:** `{"multi_select": [{"name": "tag1"}, {"name": "tag2"}]}`
- **Date:** `{"date": {"start": "2024-01-01"}}`
- **Checkbox:** `{"checkbox": true}`
- **URL:** `{"url": "https://example.com"}`
- **Email:** `{"email": "user@example.com"}`

**Example Interaction:**
- User: "Create a new task called 'Review documentation' with status 'To Do' in my Tasks database"
- Action: Create page with properties
- Output: "✓ Created new task: Review documentation (https://notion.so/...)"

---

### 4. Update Existing Pages

**When to use:** User wants to modify properties of an existing page.

**Process:**
1. Find the page ID (via search or query)
2. Extract properties to update from user request
3. Make PATCH request to `https://api.notion.com/v1/pages/{page_id}`
4. Confirm update and show changes

**API Call:**
```python
payload = {
    "properties": {
        "Status": {
            "select": {
                "name": "Done"
            }
        },
        "Completed Date": {
            "date": {
                "start": "2024-02-08"
            }
        }
    }
}

response = requests.patch(
    f"https://api.notion.com/v1/pages/{page_id}",
    headers=headers,
    json=payload
)
```

**Example Interaction:**
- User: "Mark the task 'Review documentation' as Done"
- Action: Search for page, update Status property
- Output: "✓ Updated task status to Done"

---

## Error Handling

### Common Errors and Solutions

**1. Authentication Error (401)**
- **Cause:** Invalid or missing API key
- **Solution:** Verify `config.json` has correct API key
- **Message to user:** "Authentication failed. Please check your Notion API key in config.json"

**2. Object Not Found (404)**
- **Cause:** Database/page not shared with integration or invalid ID
- **Solution:** Ensure the resource is shared with your integration
- **Message to user:** "Cannot access this resource. Make sure it's shared with your Notion integration."

**3. Validation Error (400)**
- **Cause:** Invalid property types or missing required fields
- **Solution:** Check database schema and match property types
- **Message to user:** "Invalid data format. Please check the required fields for this database."

**4. Rate Limit (429)**
- **Cause:** Too many API requests
- **Solution:** Implement exponential backoff, wait before retry
- **Message to user:** "Notion API rate limit reached. Retrying in a moment..."

**5. No Databases Found**
- **Cause:** No databases shared with integration
- **Solution:** Share at least one database with the integration
- **Message to user:** "No databases found. Share databases with your Notion integration in Notion settings."

---

## Implementation Guidelines

### Reading Configuration
```python
import json
import os

def load_notion_config():
    config_path = os.path.expanduser('~/.nanobot/config.json')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError("~/.nanobot/config.json not found. Please configure your Notion API key.")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    if 'tools' not in config or 'notion' not in config['tools'] or 'apiKey' not in config['tools']['notion']:
        raise ValueError("Notion API key not found in ~/.nanobot/config.json")
    
    return config['tools']['notion']['apiKey']
```

### Making API Requests
```python
def make_notion_request(endpoint, method='GET', data=None, api_key=None):
    """
    Make a request to Notion API with proper headers and error handling.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    url = f"https://api.notion.com/v1/{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PATCH':
            response = requests.patch(url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise Exception("Authentication failed. Check your API key.")
        elif response.status_code == 404:
            raise Exception("Resource not found. Make sure it's shared with your integration.")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded. Please wait before retrying.")
        else:
            raise Exception(f"Notion API error: {e}")
```

### Pagination Handling
Notion API returns max 100 results per request. Handle pagination:

```python
def get_all_results(endpoint, api_key):
    all_results = []
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {}
        if start_cursor:
            payload['start_cursor'] = start_cursor
        
        response = make_notion_request(endpoint, 'POST', payload, api_key)
        all_results.extend(response.get('results', []))
        
        has_more = response.get('has_more', False)
        start_cursor = response.get('next_cursor')
    
    return all_results
```

---

## Example Usage Scenarios

### Scenario 1: Quick Task Creation
**User:** "Add a task 'Call client' to my Tasks database with high priority"

**Bot Actions:**
1. List databases to find "Tasks"
2. Check database schema for property types
3. Create new page with:
    - Name: "Call client"
    - Priority: "High"
4. Return confirmation with link

### Scenario 2: Status Update
**User:** "Mark all tasks with status 'In Review' as 'Done'"

**Bot Actions:**
1. Query Tasks database with filter: Status = "In Review"
2. For each result, update Status to "Done"
3. Report number of tasks updated

### Scenario 3: Database Search
**User:** "Show me all projects due this week"

**Bot Actions:**
1. Identify "Projects" database
2. Calculate date range for current week
3. Query with date filter
4. Format and display results

---

## Best Practices

1. **Always validate database schema** before creating/updating pages
2. **Use pagination** for large result sets
3. **Cache database IDs** to reduce API calls
4. **Provide clear error messages** to users
5. **Respect rate limits** (average 3 requests per second)
6. **Format output** in a readable, structured way
7. **Confirm actions** before making destructive changes
8. **Handle null values** gracefully in properties

---


## API Version Notes

This skill uses Notion API version **2022-06-28**. Always include the `Notion-Version` header in requests.

For latest API changes, see: https://developers.notion.com/reference/changes-by-version