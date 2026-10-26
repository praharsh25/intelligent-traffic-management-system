"""End-to-End integration test simulating dashboard client interactions."""

import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_e2e.db")
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": test_db,
        "AUTOSTART_WORKER": False,
        "DEFAULT_SPEED": 1.0,
    })
    with app.test_client() as test_client:
        yield test_client


def test_full_dashboard_flow(client):
    # 1. Fetch dashboard HTML
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "TRAFFIC" in html
    assert "SIMULATED DATA" in html
    assert "chart-queue-throughput" in html
    assert "junction-grid" in html

    # 2. Query initial state
    res = client.get("/api/state")
    assert res.status_code == 200
    state = res.get_json()
    assert len(state["intersections"]) == 4

    # 3. Advance simulation multiple ticks
    for _ in range(5):
        res = client.post("/api/tick")
        assert res.status_code == 200

    # 4. Check timeline chart data
    res = client.get("/api/analytics/chart-data")
    assert res.status_code == 200
    cdata = res.get_json()
    assert "timeline" in cdata
    assert len(cdata["timeline"]) >= 1

    # 5. Check summary analytics
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    sdata = res.get_json()
    assert "avg_wait_seconds" in sdata
    assert "signal_utilization" in sdata

    # 6. Execute comparative baseline benchmark
    res = client.post(
        "/api/analytics/compare-baseline",
        json={"duration_ticks": 15, "seed": 42, "scenario": "medium"},
    )
    assert res.status_code == 200
    bdata = res.get_json()
    assert bdata["status"] == "success"
    assert "wait_reduction_pct" in bdata["comparison"]
