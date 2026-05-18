from pathlib import Path


def test_runs_page_exposes_delete_action_in_history_table():
    source = Path("frontend/src/pages/RunsPage.vue").read_text(encoding="utf-8")

    assert "Trash2" in source
    assert "api.deleteRun(run.id)" in source
    assert "删除" in source


def test_run_detail_formats_zero_cost_as_unknown_not_valid_price():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    detail_source = Path("frontend/src/pages/RunDetailPage.vue").read_text(encoding="utf-8")

    assert "formatRunCost" in source
    assert "value <= 0" in source
    assert "<$0.0001" in source
    assert "formatRunCost(run.cost_usd)" in detail_source
