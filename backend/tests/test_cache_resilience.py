import json

from src import cache


class FakeRedis:
    def __init__(self, values=None, fail_get=False, fail_set=False, fail_delete=False):
        self.values = dict(values or {})
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.fail_delete = fail_delete
        self.deleted = []

    def get(self, key):
        if self.fail_get:
            raise TimeoutError("redis unavailable")
        return self.values.get(key)

    def set(self, key, value, ex):
        if self.fail_set:
            raise TimeoutError("redis unavailable")
        self.values[key] = value
        return True

    def delete(self, *keys):
        if self.fail_delete:
            raise TimeoutError("redis unavailable")
        self.deleted.extend(keys)
        count = 0
        for key in keys:
            count += int(key in self.values)
            self.values.pop(key, None)
        return count


def test_cache_reads_and_decodes_json(monkeypatch):
    client = FakeRedis({"registry:lookup:reg:ABC": json.dumps({"found": True})})
    monkeypatch.setattr(cache, "_client", lambda: client)

    assert cache.get_json("registry:lookup:reg:ABC") == {"found": True}


def test_cache_miss_and_malformed_json_are_safe_misses(monkeypatch):
    client = FakeRedis({"bad": "{not-json"})
    monkeypatch.setattr(cache, "_client", lambda: client)

    assert cache.get_json("missing") is None
    assert cache.get_json("bad") is None


def test_cache_backend_outage_fails_open_for_cache_reads_and_writes(monkeypatch):
    client = FakeRedis(fail_get=True, fail_set=True, fail_delete=True)
    monkeypatch.setattr(cache, "_client", lambda: client)

    assert cache.get_json("registry:lookup:reg:ABC") is None
    assert cache.set_json("registry:lookup:reg:ABC", {"found": True}, 30) is False
    assert cache.invalidate_lookup_keys(["registry:lookup:reg:ABC"]) == 0


def test_cache_writes_with_ttl_and_invalidates_only_requested_keys(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(cache, "_client", lambda: client)

    assert cache.set_json("key-a", {"value": 1}, 30) is True
    assert json.loads(client.values["key-a"]) == {"value": 1}
    assert cache.set_json("key-b", {"value": 2}, 30) is True

    assert cache.invalidate_lookup_keys(["key-a"]) == 1
    assert "key-a" not in client.values
    assert "key-b" in client.values
