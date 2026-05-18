from pydantic_ai.usage import RunUsage

from backend.cost_tracker import calc_cost


def test_openai_gpt55_cost_uses_fallback_for_unhyphenated_model_name(monkeypatch):
    usage = RunUsage(input_tokens=1_500, output_tokens=200, cache_read_tokens=500)
    calc_calls = []

    def fake_calc_price(usage, model_name, *, provider_id):
        calc_calls.append((model_name, provider_id))
        raise LookupError("not in pricing catalog")

    monkeypatch.setattr("backend.cost_tracker.calc_price", fake_calc_price)

    cost = calc_cost(usage, "gpt5.5", provider_spec="openai")

    assert calc_calls == [("gpt-5.5", "openai")]
    assert cost == 0.005625
