"""Toggl API wrapper for timer operations."""

import codecs
import datetime
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
        self.report_url = "https://api.track.toggl.com/reports/api/v3"
        auth_string = f"{self.api_token}:api_token"
        auth_value = "Basic " + b64encode(auth_string.encode("ascii")).decode("ascii")
        self.headers = {
            "content-type": "application/json",
            "Authorization": auth_value,
        }

    def load_api_token(self):
        """Load API token from environment or ~/.env file."""
        # Check environment variable first
        token = os.environ.get("TOGGL_API_TOKEN")
        if token:
            self.api_token = token
            return

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
                    key = key.removeprefix("export ").strip()
                    value = value.strip().strip("'\"")
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

    def get_clients(self, workspace_id):
        """Get all clients in a workspace."""
        return self.get(f"/workspaces/{workspace_id}/clients")

    def get_projects(self, workspace_id):
        """Get all projects in a workspace."""
        return self.get(
            f"/workspaces/{workspace_id}/projects", params={"per_page": 500}
        )

    def get_tags(self, workspace_id):
        """Get all tags in a workspace."""
        return self.get(f"/workspaces/{workspace_id}/tags")

    def time_entries_between(self, start_date, end_date):
        """Get time entries between two dates (inclusive, local time). Dates are date objects."""
        local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        start = datetime.datetime.combine(
            start_date, datetime.time.min, tzinfo=local_tz
        )
        end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=local_tz
        )
        params = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        return self.get("/me/time_entries", params=params)

    def recent_entries(self, limit=10):
        """Get recent time entries (most recent first)."""
        return self.get("/me/time_entries")[:limit]

    def current_timer(self):
        """Get the currently running time entry, or None."""
        result = self.get("/me/time_entries/current")
        return result

    def start_timer(
        self, description, workspace_id, project_id=None, tags=None, start_time=None
    ):
        """Start a new time entry. start_time is an optional datetime (UTC)."""
        if start_time is None:
            start_time = datetime.datetime.now(datetime.timezone.utc)

        data = {
            "description": description,
            "workspace_id": workspace_id,
            "start": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
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

    def summary_report_csv(
        self, workspace_id, start_date, end_date, client_ids=None, tag_ids=None
    ):
        """Fetch summary CSV from the Toggl Reports API."""
        url = f"{self.report_url}/workspace/{workspace_id}/summary/time_entries.csv"
        body = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        if client_ids:
            body["client_ids"] = list(client_ids)
        if tag_ids:
            body["tag_ids"] = list(tag_ids)

        response = requests.post(url, headers=self.headers, json=body)
        response.raise_for_status()
        return self._decode_bom_text(response.content)

    @staticmethod
    def _decode_bom_text(raw_data):
        """Decode CSV text that may start with a BOM."""
        for bom, encoding in (
            (codecs.BOM_UTF8, "utf-8"),
            (codecs.BOM_UTF16_LE, "utf-16le"),
            (codecs.BOM_UTF16_BE, "utf-16be"),
            (codecs.BOM_UTF32_LE, "utf-32le"),
            (codecs.BOM_UTF32_BE, "utf-32be"),
        ):
            if raw_data.startswith(bom):
                raw_data = raw_data[len(bom) :]
                return raw_data.decode(encoding)

        return raw_data.decode("utf-8")
