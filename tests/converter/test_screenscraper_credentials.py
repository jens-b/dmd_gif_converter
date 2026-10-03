import sys
from types import SimpleNamespace

from src.engine.media_sources.screenscraper import (
    ScreenScraperCredentialStore,
    ScreenScraperCredentials,
)


def test_screenscraper_credentials_are_saved_and_loaded_from_keyring(monkeypatch):
    stored = {}
    fake_keyring = SimpleNamespace(
        get_password=lambda service, account: stored.get((service, account)),
        set_password=lambda service, account, value: stored.__setitem__(
            (service, account), value
        ),
        delete_password=lambda service, account: stored.pop((service, account), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = ScreenScraperCredentialStore()
    credentials = ScreenScraperCredentials(
        username="player",
        password="member-secret",
        developer_id="dev-123",
        developer_password="developer-secret",
    )

    store.save(credentials)

    assert store.load() == credentials
    assert all("secret" not in account for _, account in stored)
    assert len(stored) == 4


def test_screenscraper_credentials_can_be_cleared(monkeypatch):
    stored = {}
    fake_keyring = SimpleNamespace(
        get_password=lambda service, account: stored.get((service, account)),
        set_password=lambda service, account, value: stored.__setitem__(
            (service, account), value
        ),
        delete_password=lambda service, account: stored.pop((service, account), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = ScreenScraperCredentialStore()
    store.save(ScreenScraperCredentials(username="player", password="secret"))

    store.save(ScreenScraperCredentials())

    assert store.load() == ScreenScraperCredentials()
    assert stored == {}
