from solarsponge.config import load_config


def test_config_hash_stable():
    a = load_config()
    b = load_config()
    assert a.config_hash() == b.config_hash()
    assert len(a.config_hash()) == 16


def test_pulp_pin_documented():
    text = open("pyproject.toml").read()
    assert "pulp==2.9.0" in text
