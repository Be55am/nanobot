# Notion Skill

This skill will provide commands to interact with the Notion API.

## Requirements
- Python 3.11
- `notion-client` library
- A Notion integration token and database ID.

## Commands
1. `notion list [database_id]` – List items in a database.
2. `notion add [database_id] "title"` – Add a new page.
3. `notion update [page_id] "property"="value"` – Update a property.
4. `notion delete [page_id]` – Delete a page.

## Usage
```bash
nanobot agent -m "notion list my_database_id"
```
