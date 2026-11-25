import json
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config


@pytest.fixture
def live_config(tmp_path, monkeypatch):
    """Use fictional credentials and fail on any real network access."""
    for name, value in {
        "DATA_DIR": tmp_path,
        "EXPORT_FORMAT": "json",
        "INSTAGRAM_TARGETS": [],
        "TWITTER_SEARCH_QUERIES": [],
        "YOUTUBE_SEARCH_QUERIES": [],
        "YOUTUBE_API_KEY": "sample youtube key+/=",
        "TWITTER_BEARER_TOKEN": "sample bearer token+/=",
        "WEBSCRAPING_AI_KEY": "sample proxy key+/=",
    }.items():
        monkeypatch.setattr(config, name, value)

    attempts = []

    def forbid(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("Network access is forbidden in tests")

    monkeypatch.setattr(socket.socket, "connect", forbid)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    yield
    assert not attempts


@pytest.fixture
def mock_instagram(monkeypatch):
    from scrapers import instagram

    response = Mock(status_code=200)
    response.json.return_value = {
        "graphql": {"user": {
            "full_name": "Fictional profile",
            "biography": "Sample bio",
            "edge_followed_by": {"count": 100},
            "edge_owner_to_timeline_media": {"count": 1, "edges": [
                {"node": {"shortcode": "sample-post", "edge_liked_by": {"count": 10}}},
            ]},
        }},
    }
    get = Mock(return_value=response)
    monkeypatch.setattr(instagram.requests_html.HTMLSession, "get", get)
    return get


@pytest.fixture
def mock_twitter(monkeypatch):
    from scrapers import twitter

    def configure(*responses):
        connections = []
        for response in responses:
            conn = Mock()
            if isinstance(response, Exception):
                conn.getresponse.side_effect = response
            else:
                status, body = response
                conn.getresponse.return_value = SimpleNamespace(
                    status=status,
                    read=Mock(return_value=json.dumps(body).encode("utf-8")),
                )
            connections.append(conn)
        connect = Mock(side_effect=connections)
        monkeypatch.setattr(twitter.http.client, "HTTPSConnection", connect)
        return connect, connections

    return configure


@pytest.fixture
def mock_youtube(monkeypatch):
    from scrapers import youtube

    service = Mock()
    service.search.return_value.list.return_value.execute.return_value = {
        "items": [{"id": {"videoId": "sample-video"}}],
    }
    service.videos.return_value.list.return_value.execute.return_value = {
        "items": [{
            "id": "sample-video",
            "snippet": {"title": "Fictional video"},
            "statistics": {"viewCount": "200", "likeCount": "12"},
        }],
    }
    build = Mock(return_value=service)
    monkeypatch.setattr(youtube, "build", build)
    return build, service
