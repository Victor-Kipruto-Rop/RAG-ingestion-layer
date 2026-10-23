import json

from src import cache


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}
        self.deleted = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value
        self.expirations[key] = ex
        return True

    def delete(self, *keys):
        self.deleted.extend(keys)
        removed = 0
        for key in keys:
            removed += int(self.values.pop(key, None) is not None)
            self.expirations.pop(key, None)
        return removed


def test_cache_round_trip_applies_ttl_and_invalidates_keys(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(cache, "_client", lambda: client)

    assert cache.set_json("registry:lookup:reg:REG-1", {"found": True}, 300) is True
    assert client.expirations["registry:lookup:reg:REG-1"] == 300
    assert cache.get_json("registry:lookup:reg:REG-1") == {"found": True}
    assert json.loads(client.values["registry:lookup:reg:REG-1"]) == {"found": True}

    removed = cache.invalidate_lookup_keys(["registry:lookup:reg:REG-1"])
    assert removed == 1
    assert cache.get_json("registry:lookup:reg:REG-1") is None


def test_cache_failure_falls_back_to_authoritative_database(monkeypatch):
    class UnavailableRedis:
        def get(self, key):
            raise ConnectionError("redis unavailable")

        def set(self, key, value, ex):
            raise ConnectionError("redis unavailable")

        def delete(self, *keys):
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr(cache, "_client", lambda: UnavailableRedis())

    assert cache.get_json("registry:lookup:reg:REG-2") is None
    assert cache.set_json("registry:lookup:reg:REG-2", {"found": True}, 60) is False
    assert cache.invalidate_lookup_keys(["registry:lookup:reg:REG-2"]) == 0
