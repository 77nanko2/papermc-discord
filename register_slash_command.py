import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

commands = {
    "name": "server",
    "description": "サーバーのコントロール",
    "options": [
        {
            "name": "action",
            "description": "start/stop/status",
            "type": 3,
            "required": True,
            "choices": [
                {"name": "start", "value": "start"},
                {"name": "stop", "value": "stop"},
                {"name": "status", "value": "status"},
            ],
        },
    ],
}


def main():
    url = f"https://discord.com/api/v10/applications/{os.environ['DISCORD_APP_ID']}/commands"
    headers = {
        "Authorization": f'Bot {os.environ["DISCORD_TOKEN"]}',
        "Content-Type": "application/json",
    }
    res = requests.post(url, headers=headers, data=json.dumps(commands))
    print(res.content)


if __name__ == "__main__":
    main()
