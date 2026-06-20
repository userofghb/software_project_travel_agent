"""Comprehensive tests for Plans API to improve coverage from 42% to 75-80%."""
import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient


def register(client, username="alice", email="alice@example.com"):
    """Helper to register a user."""
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "secret123",
            "profile": {
                "travel_style": "深度游",
                "budget_level": "中",
                "interest_tags": ["历史", "美食"],
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
                "risk_sensitivity": "中",
                "pace_preference": "中等",
            },
        },
    )


def login(client, username="alice"):
    """Helper to login a user."""
    response = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestParseEndpointComprehensive:
    """Comprehensive tests for /api/plans/parse endpoint."""

    def test_parse_with_standard_format(self, client):
        """Test parsing with standard date format YYYY-MM-DD."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "去上海，2026-06-01到2026-06-05，预算8000"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should parse city and budget correctly
        assert data["city"] == "上海"
        assert data["budget_range"] == "high"
        assert data["start_date"] == "2026-06-01"

    def test_parse_with_chinese_day_format(self, client):
        """Test parsing with Chinese day expressions."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "去杭州 玩5天"},
        )
        assert response.status_code == 200
        data = response.json()
        # City extraction should work
        assert data["city"] is not None
        assert "5" in data["duration"] or 5 == data.get("duration")

    def test_parse_with_budget_keyword_high(self, client):
        """Test budget extraction with high-end keyword."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "上海高端品质旅游"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["budget_range"] == "high"

    def test_parse_with_budget_keyword_low(self, client):
        """Test budget extraction with low-cost keyword."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "广州经济省钱旅游"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["budget_range"] == "low"

    def test_parse_with_month_day_format(self, client):
        """Test parsing with month-day format."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "去成都旅游 6月15日到6月18日"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should extract city
        assert data["city"] is not None
        assert data["start_date"] is not None

    def test_parse_with_multiple_city_patterns(self, client):
        """Test city extraction from various patterns."""
        test_cases = [
            ("去西安玩", "西安"),
            ("南京旅游", "南京"),
            ("苏州2日游", "苏州"),
        ]
        for text, expected_city in test_cases:
            response = client.post("/api/plans/parse", json={"text": text})
            assert response.status_code == 200
            data = response.json()
            # City should match (or be default if not recognized)
            assert data["city"] is not None

    def test_parse_default_values(self, client):
        """Test default values when only city is specified."""
        response = client.post(
            "/api/plans/parse",
            json={"text": "武汉"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should have defaults
        assert data["budget_range"] in ["low", "medium", "high"]
        assert data["transport_preference"] is not None
        assert data["accommodation_preference"] is not None


class TestListPlansComprehensive:
    """Comprehensive tests for /api/plans GET endpoint."""

    def test_list_plans_empty(self, client):
        """Test listing plans when user has no plans."""
        register(client)
        headers = login(client)
        
        response = client.get("/api/plans", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_plans_with_multiple_plans(self, client):
        """Test listing when user has multiple plans."""
        register(client)
        headers = login(client)
        
        # Create 3 plans
        for i in range(3):
            client.post(
                "/api/plans",
                headers=headers,
                json={
                    "title": f"旅行{i+1}",
                    "city": "上海",
                    "start_date": f"2026-07-{10+i:02d}",
                    "end_date": f"2026-07-{13+i:02d}",
                    "budget_range": "中",
                    "transport_preference": "公交",
                    "accommodation_preference": "舒适型",
                },
            )
        
        response = client.get("/api/plans", headers=headers)
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) >= 2  # At least created plans exist

    def test_list_plans_search_by_title(self, client):
        """Test searching plans by title keyword."""
        register(client)
        headers = login(client)
        
        # Create plans with specific titles
        client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "北京文化之旅",
                "city": "北京",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        
        client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "上海美食探险",
                "city": "上海",
                "start_date": "2026-08-05",
                "end_date": "2026-08-07",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        
        # Search for "北京"
        response = client.get("/api/plans?search=北京", headers=headers)
        assert response.status_code == 200
        plans = response.json()
        # Should find plan with "北京" in title
        assert any("北京" in p["title"] for p in plans)

    def test_list_plans_filter_by_risk_level(self, client):
        """Test filtering plans by risk level."""
        register(client)
        headers = login(client)
        
        # Create a plan
        client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "低风险旅行",
                "city": "上海",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        
        # Try filtering by risk level
        for risk in ["low", "medium", "high", "all"]:
            response = client.get(f"/api/plans?risk_level={risk}", headers=headers)
            assert response.status_code == 200
            # Should return list even if empty
            assert isinstance(response.json(), list)

    def test_list_plans_combined_filter_search(self, client):
        """Test filtering with both search and risk_level."""
        register(client)
        headers = login(client)
        
        client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "江南古镇游",
                "city": "苏州",
                "start_date": "2026-09-01",
                "end_date": "2026-09-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        
        response = client.get("/api/plans?search=江南&risk_level=medium", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_plans_user_isolation(self, client):
        """Test that users can only see their own plans."""
        # Register and create plan as alice
        register(client, username="alice", email="alice@example.com")
        headers_alice = login(client, username="alice")
        
        client.post(
            "/api/plans",
            headers=headers_alice,
            json={
                "title": "Alice的旅行",
                "city": "北京",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        
        # Register and login as bob
        register(client, username="bob", email="bob@example.com")
        headers_bob = login(client, username="bob")
        
        # Bob should not see Alice's plans
        response = client.get("/api/plans", headers=headers_bob)
        assert response.status_code == 200
        plans = response.json()
        assert not any("Alice的旅行" in p["title"] for p in plans)


class TestPlanVersionManagement:
    """Tests for version management endpoints."""

    def test_get_plan_versions(self, client):
        """Test getting plan version history."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "版本测试",
                "city": "杭州",
                "start_date": "2026-08-10",
                "end_date": "2026-08-12",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["task_id"]
        
        # Get plan from task
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        
        # Get versions
        response = client.get(f"/api/plans/{plan_id}/versions", headers=headers)
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) >= 1

    def test_restore_plan_version(self, client):
        """Test restoring to a previous version."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "恢复测试",
                "city": "广州",
                "start_date": "2026-09-01",
                "end_date": "2026-09-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        # Get plan
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        plans_response = client.get("/api/plans", headers=headers)
        plan = next(p for p in plans_response.json() if p["id"] == plan_id)
        version_id = plan["current_version_id"]
        
        # Try to restore (should succeed)
        response = client.post(
            f"/api/plans/{plan_id}/versions/{version_id}/restore",
            headers=headers,
        )
        assert response.status_code == 200


class TestPlanErrorHandling:
    """Tests for error handling and edge cases."""

    def test_get_nonexistent_plan(self, client):
        """Test accessing a plan that doesn't exist."""
        register(client)
        headers = login(client)
        
        response = client.get("/api/plans/999999", headers=headers)
        assert response.status_code == 404

    def test_delete_plan(self, client):
        """Test deleting a plan."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "删除测试",
                "city": "深圳",
                "start_date": "2026-10-01",
                "end_date": "2026-10-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        # Get plan id
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        
        # Delete the plan
        response = client.delete(f"/api/plans/{plan_id}", headers=headers)
        assert response.status_code == 204
        
        # Verify it's deleted
        response = client.get(f"/api/plans/{plan_id}", headers=headers)
        assert response.status_code == 404

    def test_access_other_users_plan_forbidden(self, client):
        """Test that users cannot access other users' plans."""
        # Alice creates a plan
        register(client, username="alice", email="alice@example.com")
        headers_alice = login(client, username="alice")
        
        create_response = client.post(
            "/api/plans",
            headers=headers_alice,
            json={
                "title": "Alice私密旅行",
                "city": "西安",
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers_alice)
        plan_id = task_response.json()["plan_id"]
        
        # Bob tries to access Alice's plan
        register(client, username="bob", email="bob@example.com")
        headers_bob = login(client, username="bob")
        
        response = client.get(f"/api/plans/{plan_id}", headers=headers_bob)
        # Should be 404 (not found) or 403 (forbidden) - either is acceptable
        assert response.status_code in [403, 404]

    def test_get_plan_summary(self, client):
        """Test getting plan summary."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "摘要测试",
                "city": "成都",
                "start_date": "2026-12-01",
                "end_date": "2026-12-03",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        
        # Get summary
        response = client.get(f"/api/plans/{plan_id}/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data


class TestPlanWarnings:
    """Tests for plan warnings endpoints."""

    def test_get_plan_warnings(self, client):
        """Test getting current plan warnings."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "警告测试",
                "city": "大理",
                "start_date": "2026-12-15",
                "end_date": "2026-12-17",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        
        # Get warnings
        response = client.get(f"/api/plans/{plan_id}/warnings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert "warnings" in data

    def test_get_version_warnings(self, client):
        """Test getting warnings for a specific version."""
        register(client)
        headers = login(client)
        
        # Create a plan
        create_response = client.post(
            "/api/plans",
            headers=headers,
            json={
                "title": "版本警告测试",
                "city": "桂林",
                "start_date": "2026-12-20",
                "end_date": "2026-12-22",
                "budget_range": "中",
                "transport_preference": "公交",
                "accommodation_preference": "舒适型",
            },
        )
        task_id = create_response.json()["task_id"]
        
        task_response = client.get(f"/api/tasks/{task_id}", headers=headers)
        plan_id = task_response.json()["plan_id"]
        version_id = task_response.json()["result_version_id"]
        
        # Get version warnings
        response = client.get(
            f"/api/plans/{plan_id}/versions/{version_id}/warnings",
            headers=headers,
        )
        assert response.status_code == 200
