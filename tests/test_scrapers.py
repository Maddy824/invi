import json
import logging
import runpy
import urllib.parse
from pathlib import Path
from unittest.mock import Mock

import httplib2
import pytest
from googleapiclient.errors import HttpError
from requests.exceptions import ConnectTimeout, ReadTimeout

import config
from scrapers import base, instagram, twitter, youtube


pytestmark = pytest.mark.usefixtures("live_config")


def test_youtube_error_does_not_expose_key(mock_youtube, caplog):
    _, service = mock_youtube
    secret = config.YOUTUBE_API_KEY
    encoded = urllib.parse.quote_plus(secret)
    service.search.return_value.list.return_value.execute.side_effect = HttpError(
        httplib2.Response({"status": "403"}),
        json.dumps({"error": {"message": secret}}).encode(),
        uri=f"https://example.invalid/?key={encoded}",
    )

    result = youtube.YouTubeScraper().scrape("sample")
    assert result.errors == ["YouTube API request failed (HTTP 403)"]
    diagnostic = caplog.text + json.dumps(result.to_dict())
    assert secret not in diagnostic
    assert encoded not in diagnostic


@pytest.mark.parametrize("stage", ["search", "videos"])
@pytest.mark.parametrize("malformed", [False, True])
def test_youtube_transport_error_does_not_log_upstream_details(monkeypatch, caplog, stage, malformed):
    secret = config.YOUTUBE_API_KEY
    encoded = urllib.parse.quote_plus(secret)
    details = f"private upstream response: {secret} {encoded}"
    content = details.encode() if malformed else json.dumps({
        "error": {"message": details, "errors": [{"reason": details}]},
    }).encode()
    responses = []
    if stage == "videos":
        responses.append((
            httplib2.Response({"status": "200"}),
            b'{"items": [{"id": {"videoId": "sample-video"}}]}',
        ))
    responses.append((httplib2.Response({"status": "403"}), content))
    request = Mock(side_effect=responses)
    monkeypatch.setattr(httplib2.Http, "request", request)
    for name in ("googleapiclient.discovery", "googleapiclient.http", "googleapiclient.model"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)
        caplog.set_level(logging.DEBUG, logger=name)

    result = youtube.YouTubeScraper().scrape("sample")

    assert request.call_count == len(responses)
    assert f"/{stage}?" in request.call_args.args[0]
    assert encoded in request.call_args.args[0]
    assert result.errors == ["YouTube API request failed (HTTP 403)"]
    assert result.errors[0] in caplog.text
    diagnostic = caplog.text + json.dumps(result.to_dict())
    assert "private upstream response" not in diagnostic
    assert secret not in diagnostic
    assert encoded not in diagnostic


def test_twitter_token_not_logged_on_success(mock_twitter, caplog):
    guest = "sample guest token+/="
    connect, connections = mock_twitter(
        (200, {"guest_token": guest}),
        (200, {"globalObjects": {"tweets": {"sample": {"full_text": "Fictional post"}}}}),
    )
    with caplog.at_level(logging.INFO):
        result = twitter.TwitterScraper().scrape("sample")

    assert not result.errors
    assert len(result.posts) == 1
    assert "Acquired Twitter guest token" in caplog.text
    assert guest not in caplog.text
    assert config.TWITTER_BEARER_TOKEN not in caplog.text
    assert config.WEBSCRAPING_AI_KEY not in caplog.text
    assert connect.call_count == 2
    for conn in connections:
        conn.close.assert_called_once()


def test_twitter_error_does_not_expose_credentials(mock_twitter, caplog):
    guest = "sample guest token+/="
    secrets = [config.TWITTER_BEARER_TOKEN, config.WEBSCRAPING_AI_KEY, guest]
    details = " ".join(secrets + [urllib.parse.quote_plus(secret) for secret in secrets])
    mock_twitter((200, {"guest_token": guest}), RuntimeError(details))

    with caplog.at_level(logging.INFO):
        result = twitter.TwitterScraper().scrape("sample")

    assert result.errors
    diagnostic = caplog.text + json.dumps(result.to_dict())
    for secret in secrets:
        assert secret not in diagnostic
        assert urllib.parse.quote_plus(secret) not in diagnostic


@pytest.mark.parametrize("status,body", [
    (200, {"errors": ["sample proxy key+/="]}),
    (200, {"guest_token": ""}),
    (200, {"guest_token": 123}),
    (403, {"guest_token": "sample guest token+/="}),
    (200, []),
])
def test_twitter_rejects_bad_guest_response(mock_twitter, caplog, status, body):
    connect, connections = mock_twitter((status, body))
    result = twitter.TwitterScraper().scrape("sample")
    assert result.errors
    assert not result.posts
    assert config.WEBSCRAPING_AI_KEY not in caplog.text + json.dumps(result.to_dict())
    connect.assert_called_once()
    connections[0].close.assert_called_once()


@pytest.mark.parametrize("status,body", [
    (429, {}),
    (200, {"errors": [{"message": "upstream unavailable"}]}),
    (200, {"globalObjects": {}}),
    (200, {"globalObjects": {"tweets": []}}),
])
def test_twitter_rejects_bad_search_response(mock_twitter, status, body):
    _, connections = mock_twitter(
        (200, {"guest_token": "fictional-guest"}),
        (status, body),
    )
    result = twitter.TwitterScraper().scrape("sample")
    assert result.errors
    assert not result.posts
    for conn in connections:
        conn.close.assert_called_once()


def test_twitter_accepts_empty_search(mock_twitter):
    mock_twitter(
        (200, {"guest_token": "fictional-guest"}),
        (200, {"globalObjects": {"tweets": {}}}),
    )
    result = twitter.TwitterScraper().scrape("sample")
    assert not result.errors
    assert not result.posts


@pytest.mark.parametrize("stage", ["search", "videos"])
def test_youtube_rejects_error_response(mock_youtube, stage):
    _, service = mock_youtube
    getattr(service, stage).return_value.list.return_value.execute.return_value = {
        "error": {"message": "upstream unavailable"},
    }
    result = youtube.YouTubeScraper().scrape("sample")
    assert result.errors
    assert not result.videos


def test_youtube_accepts_empty_search(mock_youtube):
    _, service = mock_youtube
    service.search.return_value.list.return_value.execute.return_value = {"items": []}
    result = youtube.YouTubeScraper().scrape("sample")
    assert not result.errors
    assert not result.videos
    service.videos.assert_not_called()


@pytest.mark.parametrize("error", [ConnectTimeout, ReadTimeout])
def test_instagram_bounded_timeout_and_retries(mock_instagram, monkeypatch, caplog, error):
    mock_instagram.side_effect = error("private upstream details")
    monkeypatch.setattr(base.time, "sleep", Mock())

    result = instagram.InstagramScraper().scrape("sample")

    assert result.errors == ["Request timed out"]
    assert not result.profiles
    assert mock_instagram.call_count == 3
    for call in mock_instagram.call_args_list:
        assert call.kwargs["timeout"] == (30, 30)
    assert "private upstream details" not in caplog.text


@pytest.mark.parametrize("stage", ["connect", "read"])
def test_twitter_bounded_socket_timeout(mock_twitter, stage):
    connect, connections = mock_twitter((200, {"guest_token": "fictional-guest"}))
    if stage == "connect":
        connections[0].request.side_effect = TimeoutError("private upstream details")
    else:
        connections[0].getresponse.return_value.read.side_effect = TimeoutError("private upstream details")

    result = twitter.TwitterScraper().scrape("sample")

    assert result.errors == ["Request timed out"]
    connect.assert_called_once_with(twitter.API_HOST, timeout=30)
    connections[0].close.assert_called_once()


@pytest.mark.parametrize("env_value,expected", [(None, False), ("false", False), ("true", True)])
def test_browser_sandbox_is_opt_in(monkeypatch, env_value, expected):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", Mock())
    if env_value is None:
        monkeypatch.delenv("CHROME_NO_SANDBOX", raising=False)
    else:
        monkeypatch.setenv("CHROME_NO_SANDBOX", env_value)
    settings = runpy.run_path(str(Path(config.__file__)))
    assert settings["CHROME_NO_SANDBOX"] is expected
    monkeypatch.setattr(config, "CHROME_NO_SANDBOX", settings["CHROME_NO_SANDBOX"])
    chrome = Mock()
    monkeypatch.setattr(base.webdriver, "Chrome", chrome)
    monkeypatch.setattr(base, "stealth", Mock())
    with instagram.InstagramScraper() as scraper:
        scraper.get_browser()
    options = chrome.call_args.kwargs["options"]
    assert ("--no-sandbox" in options.arguments) is expected
    chrome.return_value.quit.assert_called_once()
