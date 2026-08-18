"""
Tests for restocking API endpoints.

Note on isolation: POST /api/restock-orders appends to a module-level list that persists
for the whole test session. These tests therefore never assert an exact number of
submitted orders - only that a specific order_number is present.
"""
import pytest
from datetime import datetime


# Mirrors CATEGORY_LEAD_TIME_DAYS in server/main.py. Duplicated deliberately so the test
# fails if someone changes the lead times without meaning to.
EXPECTED_LEAD_TIMES = {
    "Circuit Boards": 21,
    "Sensors": 14,
    "Actuators": 18,
    "Controllers": 10,
    "Power Supplies": 7,
}


class TestRestockCandidateEndpoints:
    """Test suite for the restocking recommendation endpoint."""

    def test_get_restock_candidates(self, client):
        """Test getting all restocking candidates."""
        response = client.get("/api/restock-candidates")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        candidate = data[0]
        for field in [
            "sku", "name", "category", "warehouse", "unit_cost",
            "quantity_on_hand", "reorder_point", "current_demand",
            "forecasted_demand", "trend", "shortfall", "urgency",
            "recommended_quantity", "line_cost", "lead_time_days",
        ]:
            assert field in candidate, f"missing field {field}"

    def test_restock_candidates_have_positive_shortfall(self, client):
        """Test that every candidate is genuinely short of stock."""
        response = client.get("/api/restock-candidates")
        data = response.json()

        for candidate in data:
            assert candidate["shortfall"] > 0
            assert candidate["forecasted_demand"] > candidate["quantity_on_hand"]
            assert candidate["shortfall"] == (
                candidate["forecasted_demand"] - candidate["quantity_on_hand"]
            )

    def test_restock_candidates_sorted_by_urgency(self, client):
        """Test that candidates come back ranked most urgent first."""
        response = client.get("/api/restock-candidates")
        data = response.json()

        urgencies = [c["urgency"] for c in data]
        assert urgencies == sorted(urgencies, reverse=True)

    def test_restock_candidate_urgency_is_a_ratio(self, client):
        """Test that urgency is shortfall relative to stock on hand, not raw units."""
        response = client.get("/api/restock-candidates")
        data = response.json()

        for candidate in data:
            expected = candidate["shortfall"] / candidate["quantity_on_hand"]
            assert abs(candidate["urgency"] - expected) < 0.001

    def test_restock_candidate_line_cost_calculation(self, client):
        """Test that line cost equals recommended quantity times unit cost."""
        response = client.get("/api/restock-candidates")
        data = response.json()

        for candidate in data:
            calculated = candidate["recommended_quantity"] * candidate["unit_cost"]
            assert abs(candidate["line_cost"] - calculated) < 0.01

    def test_restock_candidates_by_warehouse(self, client):
        """Test filtering candidates by warehouse."""
        response = client.get("/api/restock-candidates?warehouse=Tokyo")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for candidate in data:
            assert candidate["warehouse"] == "Tokyo"

    def test_restock_candidates_by_category(self, client):
        """Test filtering candidates by category."""
        response = client.get("/api/restock-candidates?category=Actuators")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for candidate in data:
            assert candidate["category"].lower() == "actuators"

    def test_restock_candidates_multiple_filters(self, client):
        """Test filtering candidates by warehouse and category together."""
        response = client.get(
            "/api/restock-candidates?warehouse=Tokyo&category=Power Supplies"
        )
        assert response.status_code == 200

        data = response.json()
        for candidate in data:
            assert candidate["warehouse"] == "Tokyo"
            assert candidate["category"].lower() == "power supplies"

    def test_restock_candidates_unknown_warehouse_is_empty(self, client):
        """Test that an unmatched warehouse yields no candidates."""
        response = client.get("/api/restock-candidates?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []

    def test_restock_candidate_lead_times_match_category(self, client):
        """Test that each candidate's lead time matches its category."""
        response = client.get("/api/restock-candidates")
        data = response.json()

        for candidate in data:
            expected = EXPECTED_LEAD_TIMES[candidate["category"]]
            assert candidate["lead_time_days"] == expected


class TestRestockOrderEndpoints:
    """Test suite for submitting and listing restocking orders."""

    def test_create_restock_order(self, client):
        """Test submitting a restocking order."""
        response = client.post(
            "/api/restock-orders",
            json={
                "budget": 150000,
                "items": [
                    {"sku": "MCU-401", "quantity": 300},
                    {"sku": "PCB-001", "quantity": 170},
                ],
            },
        )
        assert response.status_code == 200

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 150000
        assert len(order["items"]) == 2

        calculated = sum(line["line_total"] for line in order["items"])
        assert abs(order["total_value"] - calculated) < 0.01

    def test_restock_order_line_totals(self, client):
        """Test that each line total equals quantity times unit price."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 5000, "items": [{"sku": "MCU-401", "quantity": 300}]},
        )
        assert response.status_code == 200

        for line in response.json()["items"]:
            assert abs(line["line_total"] - line["quantity"] * line["unit_price"]) < 0.01

    def test_created_restock_order_appears_in_list(self, client):
        """Test that a submitted order shows up in the order list."""
        created = client.post(
            "/api/restock-orders",
            json={"budget": 10000, "items": [{"sku": "LED-406", "quantity": 120}]},
        ).json()

        response = client.get("/api/restock-orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        order_numbers = [o["order_number"] for o in data]
        assert created["order_number"] in order_numbers

    def test_restock_orders_newest_first(self, client):
        """Test that the order list is returned newest first."""
        first = client.post(
            "/api/restock-orders",
            json={"budget": 3000, "items": [{"sku": "MCU-401", "quantity": 10}]},
        ).json()
        second = client.post(
            "/api/restock-orders",
            json={"budget": 3000, "items": [{"sku": "MCU-401", "quantity": 20}]},
        ).json()

        data = client.get("/api/restock-orders").json()
        numbers = [o["order_number"] for o in data]
        assert numbers.index(second["order_number"]) < numbers.index(first["order_number"])

    def test_restock_order_expected_delivery_uses_max_lead_time(self, client):
        """Test that expected delivery follows the slowest line, not the fastest."""
        # Controllers is 10 days, Circuit Boards is 21 - the order should take 21.
        response = client.post(
            "/api/restock-orders",
            json={
                "budget": 50000,
                "items": [
                    {"sku": "MCU-401", "quantity": 300},
                    {"sku": "PCB-001", "quantity": 170},
                ],
            },
        )
        assert response.status_code == 200

        order = response.json()
        assert order["max_lead_time_days"] == 21

        submitted = datetime.fromisoformat(order["submitted_date"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        assert (expected - submitted).days == 21

    def test_restock_order_line_lead_times_match_category(self, client):
        """Test that each order line carries its own category lead time."""
        response = client.post(
            "/api/restock-orders",
            json={
                "budget": 50000,
                "items": [
                    {"sku": "MCU-401", "quantity": 10},
                    {"sku": "SRV-302", "quantity": 5},
                ],
            },
        )
        assert response.status_code == 200

        for line in response.json()["items"]:
            assert line["lead_time_days"] == EXPECTED_LEAD_TIMES[line["category"]]

    def test_create_restock_order_ignores_client_price(self, client):
        """Test that the server prices lines from inventory, not from the payload."""
        inventory = client.get("/api/inventory").json()
        real_cost = next(i["unit_cost"] for i in inventory if i["sku"] == "MCU-401")

        response = client.post(
            "/api/restock-orders",
            json={
                "budget": 100,
                # A client trying to buy at 1 cent a unit.
                "items": [{"sku": "MCU-401", "quantity": 10, "unit_price": 0.01}],
            },
        )
        assert response.status_code == 200

        line = response.json()["items"][0]
        assert line["unit_price"] == real_cost
        assert abs(line["line_total"] - 10 * real_cost) < 0.01

    def test_create_restock_order_unknown_sku(self, client):
        """Test submitting an order for a SKU that doesn't exist."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 1000, "items": [{"sku": "NOPE-999", "quantity": 1}]},
        )
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_create_restock_order_empty_items(self, client):
        """Test submitting an order with no items."""
        response = client.post(
            "/api/restock-orders", json={"budget": 1000, "items": []}
        )
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_create_restock_order_zero_quantity(self, client):
        """Test submitting an order line with a non-positive quantity."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 1000, "items": [{"sku": "MCU-401", "quantity": 0}]},
        )
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_create_restock_order_missing_budget(self, client):
        """Test that a payload without a budget fails validation."""
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "MCU-401", "quantity": 1}]},
        )
        assert response.status_code == 422


class TestDemandInventoryIntegrity:
    """Regression guard for the forecast-to-inventory join the recommendation depends on."""

    def test_demand_forecasts_join_inventory(self, client):
        """Test that enough forecast SKUs exist in inventory to recommend against.

        The original seed data had only 1 of 9 forecast SKUs present in inventory,
        which left the restocking recommendation with a single candidate.
        """
        forecasts = client.get("/api/demand").json()
        inventory = client.get("/api/inventory").json()

        inventory_skus = {item["sku"] for item in inventory}
        joined = [f for f in forecasts if f["item_sku"] in inventory_skus]

        assert len(joined) >= 13, (
            f"only {len(joined)} of {len(forecasts)} forecast SKUs exist in inventory"
        )

    def test_restock_candidates_cover_multiple_categories(self, client):
        """Test that candidates span categories, so the category filter is meaningful."""
        data = client.get("/api/restock-candidates").json()

        categories = {c["category"] for c in data}
        warehouses = {c["warehouse"] for c in data}

        assert len(categories) >= 4, f"candidates only cover {categories}"
        assert len(warehouses) == 3, f"candidates only cover {warehouses}"
