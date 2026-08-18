"""
Tests for reports API endpoints.
"""
import pytest


class TestReportsEndpoints:
    """Test suite for reports-related endpoints."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly performance reports."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "quarter" in first
        assert "total_orders" in first
        assert "total_revenue" in first
        assert "delivered_orders" in first
        assert "avg_order_value" in first
        assert "fulfillment_rate" in first

    def test_quarterly_reports_types(self, client):
        """Test that quarterly report fields have proper numeric types."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for quarter in data:
            assert isinstance(quarter["total_orders"], int)
            assert isinstance(quarter["delivered_orders"], int)
            assert isinstance(quarter["total_revenue"], (int, float))
            assert isinstance(quarter["avg_order_value"], (int, float))
            assert isinstance(quarter["fulfillment_rate"], (int, float))
            assert quarter["total_orders"] > 0
            assert quarter["total_revenue"] >= 0
            assert 0 <= quarter["fulfillment_rate"] <= 100

    def test_quarterly_reports_sorted_by_quarter(self, client):
        """Test that quarterly reports come back in chronological order."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_avg_order_value_calculation(self, client):
        """Test that avg_order_value equals revenue divided by order count."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for quarter in data:
            expected = quarter["total_revenue"] / quarter["total_orders"]
            assert abs(quarter["avg_order_value"] - expected) < 0.01

    def test_quarterly_fulfillment_rate_calculation(self, client):
        """Test that fulfillment_rate is the delivered share of total orders."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for quarter in data:
            expected = (
                quarter["delivered_orders"] / quarter["total_orders"]
            ) * 100
            assert abs(quarter["fulfillment_rate"] - expected) < 0.1

    def test_get_quarterly_by_warehouse(self, client):
        """Test filtering quarterly reports by warehouse."""
        response = client.get("/api/reports/quarterly?warehouse=Tokyo")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Totals must match the orders actually in that warehouse.
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_get_quarterly_by_category(self, client):
        """Test filtering quarterly reports by category."""
        response = client.get("/api/reports/quarterly?category=Sensors")
        assert response.status_code == 200

        data = response.json()
        orders = client.get("/api/orders?category=Sensors").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_get_quarterly_by_status(self, client):
        """Test filtering quarterly reports by order status."""
        response = client.get("/api/reports/quarterly?status=Delivered")
        assert response.status_code == 200

        data = response.json()

        # Every remaining order is delivered, so fulfillment is always 100%.
        for quarter in data:
            assert quarter["total_orders"] == quarter["delivered_orders"]
            assert quarter["fulfillment_rate"] == 100.0

    def test_get_quarterly_by_month(self, client):
        """Test filtering quarterly reports to a single month."""
        response = client.get("/api/reports/quarterly?month=2025-02")
        assert response.status_code == 200

        data = response.json()
        # February only falls in Q1, so exactly one quarter comes back.
        assert len(data) == 1
        assert data[0]["quarter"] == "Q1-2025"

    def test_get_quarterly_by_quarter(self, client):
        """Test filtering quarterly reports by quarter."""
        response = client.get("/api/reports/quarterly?month=Q3-2025")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["quarter"] == "Q3-2025"

    def test_get_quarterly_multiple_filters(self, client):
        """Test filtering quarterly reports with multiple filters."""
        response = client.get(
            "/api/reports/quarterly?warehouse=London&category=Sensors"
        )
        assert response.status_code == 200

        data = response.json()
        orders = client.get(
            "/api/orders?warehouse=London&category=Sensors"
        ).json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_filter_reduces_results(self, client):
        """Test that filtering returns no more orders than the unfiltered call."""
        unfiltered = client.get("/api/reports/quarterly").json()
        filtered = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in filtered) < sum(
            q["total_orders"] for q in unfiltered
        )

    def test_get_monthly_trends(self, client):
        """Test getting month-over-month trends."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "month" in first
        assert "order_count" in first
        assert "revenue" in first
        assert "delivered_count" in first

    def test_monthly_trends_types(self, client):
        """Test that monthly trend fields have proper numeric types."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        for month in data:
            assert isinstance(month["order_count"], int)
            assert isinstance(month["delivered_count"], int)
            assert isinstance(month["revenue"], (int, float))
            assert month["order_count"] > 0
            assert month["revenue"] >= 0
            assert month["delivered_count"] <= month["order_count"]

    def test_monthly_trends_month_format(self, client):
        """Test that months are formatted as YYYY-MM."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        for month in data:
            assert len(month["month"]) == 7
            assert month["month"].startswith("2025-")

    def test_monthly_trends_sorted_by_month(self, client):
        """Test that monthly trends come back in chronological order."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_get_monthly_trends_by_warehouse(self, client):
        """Test filtering monthly trends by warehouse."""
        response = client.get("/api/reports/monthly-trends?warehouse=London")
        assert response.status_code == 200

        data = response.json()
        orders = client.get("/api/orders?warehouse=London").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_get_monthly_trends_by_category(self, client):
        """Test filtering monthly trends by category."""
        response = client.get(
            "/api/reports/monthly-trends?category=Circuit Boards"
        )
        assert response.status_code == 200

        data = response.json()
        orders = client.get("/api/orders?category=Circuit Boards").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_get_monthly_trends_by_status(self, client):
        """Test filtering monthly trends by order status."""
        response = client.get("/api/reports/monthly-trends?status=Shipped")
        assert response.status_code == 200

        data = response.json()

        # No shipped order is also delivered, so the delivered count is zero.
        for month in data:
            assert month["delivered_count"] == 0

    def test_get_monthly_trends_by_quarter(self, client):
        """Test filtering monthly trends by quarter returns only its months."""
        response = client.get("/api/reports/monthly-trends?month=Q2-2025")
        assert response.status_code == 200

        data = response.json()
        assert [m["month"] for m in data] == ["2025-04", "2025-05", "2025-06"]

    def test_get_monthly_trends_by_single_month(self, client):
        """Test filtering monthly trends to a single month."""
        response = client.get("/api/reports/monthly-trends?month=2025-07")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["month"] == "2025-07"

    def test_reports_match_orders_totals(self, client):
        """Test that quarterly and monthly reports agree with raw orders."""
        orders = client.get("/api/orders").json()
        quarterly = client.get("/api/reports/quarterly").json()
        monthly = client.get("/api/reports/monthly-trends").json()

        assert sum(q["total_orders"] for q in quarterly) == len(orders)
        assert sum(m["order_count"] for m in monthly) == len(orders)

        order_revenue = sum(o["total_value"] for o in orders)
        assert abs(sum(q["total_revenue"] for q in quarterly) - order_revenue) < 0.01
        assert abs(sum(m["revenue"] for m in monthly) - order_revenue) < 0.01

    def test_reports_unknown_filter_value_returns_empty(self, client):
        """Test that a filter value matching nothing returns an empty list."""
        response = client.get("/api/reports/quarterly?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []

        response = client.get("/api/reports/monthly-trends?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []

    def test_reports_filter_all_equals_unfiltered(self, client):
        """Test that passing 'all' behaves the same as omitting the filter."""
        unfiltered = client.get("/api/reports/quarterly").json()
        explicit_all = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()

        assert unfiltered == explicit_all
