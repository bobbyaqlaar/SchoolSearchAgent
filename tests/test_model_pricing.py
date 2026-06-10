import pytest

from dubai.model_pricing import (
    PricingRates,
    clear_pricing_cache,
    get_model_pricing,
    load_model_pricing,
)


@pytest.fixture(autouse=True)
def _reset_pricing_cache():
    clear_pricing_cache()
    yield
    clear_pricing_cache()


def test_load_default_pricing_file():
    table = load_model_pricing()
    assert "gpt-4o" in table
    assert table["gpt-4o"].input_per_1k == 0.0025
    assert table["gpt-4o"].output_per_1k == 0.010


def test_get_model_pricing_unknown_returns_zero():
    assert get_model_pricing("not-a-model") == PricingRates(0.0, 0.0)


def test_load_custom_pricing_file(tmp_path):
    path = tmp_path / "custom.yaml"
    path.write_text(
        "custom-model:\n  input_per_1k: 0.01\n  output_per_1k: 0.02\n",
        encoding="utf-8",
    )
    table = load_model_pricing(path=path)
    assert table["custom-model"] == PricingRates(0.01, 0.02)


def test_invalid_pricing_file_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("gpt-4o: not-a-dict\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_model_pricing(path=path)
