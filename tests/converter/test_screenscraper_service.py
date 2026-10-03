from types import SimpleNamespace

import pytest

from src.engine.media_sources.screenscraper import (
    ScreenScraperCredentials,
    ScreenScraperGame,
    ScreenScraperMedia,
    ScreenScraperSystem,
    ScreenScraperService,
)


def test_search_returns_supported_media_and_sends_credentials(monkeypatch, tmp_path):
    calls = []
    payload = {
        "response": {
            "jeu": {
                "noms": [{"region": "wor", "text": "Example Game"}],
                "medias": [
                    {
                        "type": "video",
                        "url": "https://screenscraper.fr/media/trailer.mp4",
                        "region": "wor",
                        "parent": "jeu",
                    },
                    {
                        "type": "wheel",
                        "url": "https://screenscraper.fr/media/logo.png",
                        "region": "wor",
                        "parent": "jeu",
                    },
                    {
                        "type": "video",
                        "url": "http://screenscraper.fr/media/insecure.mp4",
                        "region": "wor",
                        "parent": "jeu",
                    },
                    {
                        "type": "video",
                        "url": "https://evil-screenscraper.fr/media/wrong.mp4",
                        "region": "wor",
                        "parent": "jeu",
                    },
                ],
            }
        }
    }

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return payload

        def close(self):
            pass

    fake_requests = SimpleNamespace(
        get=lambda url, **kwargs: (
            calls.append((url, kwargs)) or FakeResponse()
        )
    )
    monkeypatch.setattr(
        ScreenScraperService, "_requests", staticmethod(lambda: fake_requests)
    )
    service = ScreenScraperService(tmp_path)
    credentials = ScreenScraperCredentials(
        "member",
        "member-password",
        "developer",
        "developer-password",
    )

    name, media = service.search_media(
        ScreenScraperGame("123", "Example Game", "1", "Test System"),
        credentials,
    )

    assert name == "Example Game"
    assert [(item.media_type, item.extension) for item in media] == [
        ("video", ".mp4"),
        ("wheel", ".png"),
    ]
    url, request = calls[0]
    assert url.endswith("jeuInfos.php")
    assert request["params"]["gameid"] == "123"
    assert request["params"]["devid"] == "developer"
    assert request["params"]["devpassword"] == "developer-password"
    assert request["params"]["ssid"] == "member"


def test_search_requires_developer_credentials_without_making_request(tmp_path):
    service = ScreenScraperService(tmp_path)

    with pytest.raises(ValueError, match="API-Entwicklerdaten"):
        service.search_media(
            ScreenScraperGame("123", "Example Game", "1", "Test System"),
            ScreenScraperCredentials(),
        )


def test_api_login_error_response_is_reported_without_echoing_response(monkeypatch, tmp_path):
    class FakeResponse:
        status_code = 200
        text = "Erreur de login: private details"

        def json(self):
            raise ValueError("not json")

        def close(self):
            pass

    monkeypatch.setattr(
        ScreenScraperService,
        "_requests",
        staticmethod(
            lambda: SimpleNamespace(
                get=lambda *args, **kwargs: FakeResponse()
            )
        ),
    )

    with pytest.raises(RuntimeError, match="Entwickler") as error:
        ScreenScraperService(tmp_path).list_systems(
            ScreenScraperCredentials(developer_id="dev", developer_password="secret")
        )

    assert "private details" not in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (403, "API-Entwickler-Zugangsdaten"),
        (429, "Thread-Limit"),
        (430, "Kontingent"),
    ],
)
def test_api_errors_are_mapped_without_exposing_request_url(
    monkeypatch, tmp_path, status, expected
):
    class FakeResponse:
        status_code = status
        text = ""

        def json(self):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(
        ScreenScraperService,
        "_requests",
        staticmethod(lambda: SimpleNamespace(get=lambda *args, **kwargs: FakeResponse())),
    )

    with pytest.raises(RuntimeError, match=expected) as error:
        ScreenScraperService(tmp_path).search_media(
            ScreenScraperGame("123", "Example", "1", "Test System"),
            ScreenScraperCredentials("member", "secret", "dev", "secret"),
        )

    assert "secret" not in str(error.value)


def test_systems_are_loaded_and_search_is_limited_to_selected_system(
    monkeypatch, tmp_path
):
    calls = []
    responses = [
        {
            "response": {
                "systemes": [
                    {"id": "1", "noms": {"nom_eu": "Mega Drive"}},
                    {"id": "2", "noms": {"nom_us": "Master System"}},
                ]
            }
        },
        {
            "response": {
                "jeux": [
                    {
                        "id": "42",
                        "noms": [{"region": "wor", "text": "Sonic"}],
                        "systeme": {"id": "1", "noms": {"nom_eu": "Mega Drive"}},
                    }
                ]
            }
        },
    ]

    class FakeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        def close(self):
            pass

    def request(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(
        ScreenScraperService,
        "_requests",
        staticmethod(lambda: SimpleNamespace(get=request)),
    )
    service = ScreenScraperService(tmp_path)
    credentials = ScreenScraperCredentials(developer_id="dev", developer_password="pw")

    systems = service.list_systems(credentials)
    games = service.search_games("Sonic", systems[1], credentials)

    assert systems == [
        ScreenScraperSystem("2", "Master System"),
        ScreenScraperSystem("1", "Mega Drive"),
    ]
    assert games == [ScreenScraperGame("42", "Sonic", "1", "Mega Drive")]
    assert calls[0][0].endswith("systemesListe.php")
    assert calls[1][0].endswith("jeuRecherche.php")
    assert calls[1][1]["params"]["recherche"] == "Sonic"
    assert calls[1][1]["params"]["systemeid"] == "1"



def test_download_media_caches_only_complete_download(tmp_path, monkeypatch):
    content = b"video contents"

    class FakeResponse:
        status_code = 200
        url = "https://screenscraper.fr/media/trailer.mp4"
        headers = {"Content-Length": str(len(content))}

        def iter_content(self, chunk_size):
            yield content[:5]
            yield content[5:]

        def close(self):
            pass

    monkeypatch.setattr(
        ScreenScraperService,
        "_requests",
        staticmethod(lambda: SimpleNamespace(get=lambda *args, **kwargs: FakeResponse())),
    )
    service = ScreenScraperService(tmp_path)
    media = ScreenScraperMedia(
        "Example — video",
        "video",
        "https://screenscraper.fr/media/trailer.mp4",
        ".mp4",
    )

    path = service.download_media(media)

    assert path is not None
    assert open(path, "rb").read() == content
    assert service.download_media(media) == path
    assert list(tmp_path.glob("*.part")) == []


def test_download_rejects_foreign_redirect(tmp_path, monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        url="https://malicious.example/trailer.mp4",
        headers={},
        close=lambda: None,
    )
    monkeypatch.setattr(
        ScreenScraperService,
        "_requests",
        staticmethod(lambda: SimpleNamespace(get=lambda *args, **kwargs: response)),
    )

    with pytest.raises(RuntimeError, match="nicht erlaubte Medienadresse"):
        ScreenScraperService(tmp_path).download_media(
            ScreenScraperMedia(
                "video",
                "video",
                "https://screenscraper.fr/media/trailer.mp4",
                ".mp4",
            )
        )
