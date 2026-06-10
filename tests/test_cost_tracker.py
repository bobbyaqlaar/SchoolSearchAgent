def test_record_computes_cost():
    from dubai.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)
    assert tracker.total_cost == 1000 / 1000 * 0.0025 + 500 / 1000 * 0.010
    summary = tracker.summary()
    assert summary["gpt-4o"].input_tokens == 1000
    assert summary["gpt-4o"].output_tokens == 500
    assert summary["gpt-4o"].cost_usd == 0.0075


def test_local_model_is_free():
    from dubai.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record("llama-3.1", input_tokens=10_000, output_tokens=5_000)
    assert tracker.total_cost == 0.0


def test_unknown_model_does_not_raise():
    from dubai.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record("mystery-model", input_tokens=100, output_tokens=100)
    assert tracker.total_cost == 0.0


def test_record_accumulates_same_model():
    from dubai.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record("gpt-4o-mini", input_tokens=1000, output_tokens=0)
    tracker.record("gpt-4o-mini", input_tokens=1000, output_tokens=0)
    assert tracker.summary()["gpt-4o-mini"].input_tokens == 2000


def test_as_callback_returns_handler():
    from langchain_core.callbacks import BaseCallbackHandler

    from dubai.cost_tracker import CostTracker

    tracker = CostTracker()
    assert isinstance(tracker.as_callback("gpt-4o"), BaseCallbackHandler)
