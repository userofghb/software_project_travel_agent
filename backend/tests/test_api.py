def register(client, username="alice", email="alice@example.com"):
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
    response = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_register_login_and_me(client):
    register_response = register(client)
    assert register_response.status_code == 201

    duplicate_response = register(client)
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "用户名已存在"

    bad_login = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "用户名或密码错误"

    headers = login(client)
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "alice"

    profile_response = client.get("/api/profile/me", headers=headers)
    assert profile_response.status_code == 200
    profile = profile_response.json()["profile"]
    assert profile["travel_style"] == "深度游"
    assert profile["interest_tags"] == ["历史", "美食"]


def test_profile_update(client):
    register(client)
    headers = login(client)

    response = client.put(
        "/api/profile/me",
        headers=headers,
        json={
            "travel_style": "休闲",
            "budget_level": "高",
            "interest_tags": ["自然"],
            "transport_preference": "打车",
            "accommodation_preference": "高端型",
            "risk_sensitivity": "高",
            "pace_preference": "松散",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["budget_level"] == "高"
    assert "自然" in data["profile_summary"]


def test_profile_interest_tags_update(client):
    register(client)
    headers = login(client)

    update_response = client.put(
        "/api/profile/me/interests",
        headers=headers,
        json={
            "interest_tags": ["美食", "博物馆", "城市漫步"],
        },
    )
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["interest_tags"] == ["美食", "博物馆", "城市漫步"]
    assert "美食" in update_data["profile_summary"]

    get_response = client.get("/api/profile/me/interests", headers=headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["interest_tags"] == ["美食", "博物馆", "城市漫步"]


def test_plan_task_version_and_warnings_flow(client):
    register(client)
    headers = login(client)

    task_response = client.post(
        "/api/plans",
        headers=headers,
        json={
            "title": "上海五一旅行",
            "city": "上海",
            "start_date": "2026-05-01",
            "end_date": "2026-05-03",
            "budget_range": "中",
            "transport_preference": "公交",
            "accommodation_preference": "舒适型",
            "notes": "想去博物馆",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["task_id"]

    status_response = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert status_response.status_code == 200
    task_data = status_response.json()
    assert task_data["status"] == "success"
    assert task_data["result_version_id"] is not None

    plans_response = client.get("/api/plans", headers=headers)
    assert plans_response.status_code == 200
    plans = plans_response.json()
    assert len(plans) == 1
    plan_id = plans[0]["id"]
    version_id = plans[0]["current_version_id"]

    versions_response = client.get(f"/api/plans/{plan_id}/versions", headers=headers)
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1

    warning_response = client.get(f"/api/plans/{plan_id}/warnings", headers=headers)
    assert warning_response.status_code == 200
    assert warning_response.json()["plan_id"] == plan_id

    edit_response = client.put(
        f"/api/plans/{plan_id}/versions/{version_id}",
        headers=headers,
        json={
            "title": "上海五一旅行-编辑版",
            "change_summary": "updated suggestions",
            "content": {
                "city": "上海",
                "start_date": "2026-05-01",
                "end_date": "2026-05-03",
                "days": [],
                "attractions": [],
                "hotel": {},
                "meals": [],
                "weather_info": [{"date": "2026-05-01", "condition": "暴雨"}],
                "budget": {"range": "中", "estimated_total": 1500},
                "warnings": [],
                "overall_suggestions": ["减少户外活动"],
            },
        },
    )
    assert edit_response.status_code == 200
    edited_version = edit_response.json()
    assert edited_version["parent_version_id"] == version_id

    regenerate_response = client.post(
        f"/api/plans/{plan_id}/versions/{edited_version['id']}/regenerate",
        headers=headers,
        json={
            "title": "上海五一旅行-再生成",
            "city": "上海",
            "start_date": "2026-05-01",
            "end_date": "2026-05-04",
            "budget_range": "高",
            "transport_preference": "打车",
            "accommodation_preference": "高端型",
            "notes": "增加室内景点",
        },
    )
    assert regenerate_response.status_code == 200
    regenerated_task = regenerate_response.json()["task_id"]
    regenerated_status = client.get(f"/api/tasks/{regenerated_task}", headers=headers)
    assert regenerated_status.status_code == 200
    assert regenerated_status.json()["status"] == "success"


def test_plan_permissions(client):
    register(client, "alice", "alice@example.com")
    register(client, "bob", "bob@example.com")
    alice_headers = login(client, "alice")
    bob_headers = login(client, "bob")

    task_response = client.post(
        "/api/plans",
        headers=alice_headers,
        json={
            "title": "北京周末游",
            "city": "北京",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "budget_range": "低",
            "transport_preference": "步行",
            "accommodation_preference": "经济型",
            "notes": "",
        },
    )
    task_id = task_response.json()["task_id"]
    alice_status = client.get(f"/api/tasks/{task_id}", headers=alice_headers).json()
    plan_id = alice_status["plan_id"]

    forbidden = client.get(f"/api/plans/{plan_id}", headers=bob_headers)
    assert forbidden.status_code == 404
