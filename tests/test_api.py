"""Tests for tgl.api."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from tgl.api import TogglAPI


@patch("tgl.api.requests.post")
def test_summary_report_csv_posts_filters_and_decodes_bom(mock_post):
    response = MagicMock()
    response.content = b"\xef\xbb\xbfUser,Project,Duration\nAlice,Work,01:00:00\n"
    response.raise_for_status.return_value = None
    mock_post.return_value = response

    api = TogglAPI(api_token="fake")
    csv_text = api.summary_report_csv(
        123,
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 7),
        client_ids=[10],
        tag_ids=[20],
    )

    assert csv_text == "User,Project,Duration\nAlice,Work,01:00:00\n"
    mock_post.assert_called_once_with(
        "https://api.track.toggl.com/reports/api/v3/workspace/123/summary/time_entries.csv",
        headers=api.headers,
        json={
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "client_ids": [10],
            "tag_ids": [20],
        },
    )


@patch("tgl.api.requests.post")
def test_summary_report_csv_surfaces_http_errors(mock_post):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("boom")
    mock_post.return_value = response

    api = TogglAPI(api_token="fake")

    with pytest.raises(requests.HTTPError, match="boom"):
        api.summary_report_csv(
            123,
            datetime.date(2026, 3, 1),
            datetime.date(2026, 3, 7),
        )
