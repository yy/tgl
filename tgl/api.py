"""Toggl API wrapper for timer operations."""

import os
from base64 import b64encode

import requests


class TogglAPI:
    """Toggl API wrapper for starting/stopping timers."""

    def __init__(self, api_token=None):
        if api_token is None:
            self.load_api_token()
        else:
            self.api_token = api_token
        self.api_url = "https://api.track.toggl.com/api/v9"
        auth_string = f"{self.api_token}:api_token"
        auth_value = "Basic " + b64encode(auth_string.encode("ascii")).decode("ascii")
        self.headers = {
            "content-type": "application/json",
            "Authorization": auth_value,
        }

    def load_api_token(self):
        """Load API token from ~/.env file."""
        home_dir = os.path.expanduser("~")
        env_path = os.path.join(home_dir, ".env")

        if not os.path.exists(env_path):
            raise FileNotFoundError(
                f"\n\nConfiguration file not found: {env_path}\n\n"
                "To fix this, create a ~/.env file with your Toggl API token:\n\n"
                "  echo 'TOGGL_API_TOKEN=your_api_token_here' >> ~/.env\n\n"
                "You can find your API token at:\n"
                "  https://track.toggl.com/profile (scroll to 'API Token')\n"
            )

        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key == "TOGGL_API_TOKEN":
                        self.api_token = value
                        return
        except IOError as e:
            raise IOError(f"Error reading {env_path}: {e}")

        raise ValueError(
            f"\n\nTOGGL_API_TOKEN not found in {env_path}\n\n"
            "Please add the following line to your ~/.env file:\n\n"
            "  TOGGL_API_TOKEN=your_api_token_here\n\n"
            "You can find your API token at:\n"
            "  https://track.toggl.com/profile (scroll to 'API Token')\n"
        )

    def get(self, endpoint, params=None):
        """GET request to Toggl API."""
        url = self.api_url + endpoint
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, data=None):
        """POST request to Toggl API."""
        url = self.api_url + endpoint
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def patch(self, endpoint):
        """PATCH request to Toggl API."""
        url = self.api_url + endpoint
        response = requests.patch(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_workspace_id(self):
        """Get workspace ID (assumes single workspace)."""
        workspaces = self.get("/workspaces")
        return workspaces[0]["id"]

    def current_timer(self):
        """Get the currently running time entry, or None."""
        result = self.get("/me/time_entries/current")
        return result

    def start_timer(self, description, workspace_id, project_id=None, tags=None):
        """Start a new time entry."""
        import datetime

        data = {
            "description": description,
            "workspace_id": workspace_id,
            "start": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),
            "duration": -1,
            "created_with": "tgl",
        }
        if project_id is not None:
            data["project_id"] = project_id
        if tags:
            data["tags"] = list(tags)

        return self.post(
            f"/workspaces/{workspace_id}/time_entries",
            data=data,
        )

    def stop_timer(self):
        """Stop the currently running time entry."""
        entry = self.current_timer()
        if entry is None:
            return None
        wid = entry["workspace_id"]
        eid = entry["id"]
        return self.patch(f"/workspaces/{wid}/time_entries/{eid}/stop")
