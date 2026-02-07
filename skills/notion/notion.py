import json, os, sys
from notion_client import Client

def load_config():
    with open('config.json') as f:
        return json.load(f)

notion = Client(auth=os.getenv('NOTION_API_KEY') or load_config().get('NOTION_API_KEY'))

def list_db():
    res = notion.databases.list()
    for db in res.get('results', []):
        title = db.get('title') or []
        if title:
            name = title[0].get('plain_text') or 'Unnamed'
        else:
            name = 'Unnamed'
        print(f"{db['id']}: {name}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: notion.py list-db')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'list-db':
        list_db()
    else:
        print('Unknown command')
