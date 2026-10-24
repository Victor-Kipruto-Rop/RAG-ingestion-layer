from src.developer_platform import developer_platform_config


def test_developer_platform_exposes_distinct_environment_origins_and_key_prefixes():
    config = developer_platform_config()
    sandbox = config["sandbox_base_url"]
    production = config["production_base_url"]

    assert sandbox.startswith("https://")
    assert production.startswith("https://")
    assert sandbox != production
    assert config["key_prefixes"] == {
        "sandbox": "pg_sandbox_",
        "production": "pg_live_",
    }
    assert "Python" in config["sdk_languages"]
    assert "JavaScript" in config["sdk_languages"]
    assert "C#" in config["sdk_languages"]


def test_platform_config_does_not_claim_both_environments_share_a_host():
    config = developer_platform_config()
    assert config["sandbox_base_url"].split("/")[2] != config["production_base_url"].split("/")[2]
