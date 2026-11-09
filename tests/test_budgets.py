def test_create_overall_and_category_budgets(client, auth, category_id):
    overall = client.post("/budgets", json={"year": 2026, "month": 3, "limit": "500"}, headers=auth)
    food = client.post(
        "/budgets",
        json={"year": 2026, "month": 3, "limit": "150.75", "category_id": category_id},
        headers=auth,
    )
    assert overall.status_code == 201
    assert food.json()["limit"] == "150.75"

    listed = client.get("/budgets", params={"year": 2026, "month": 3}, headers=auth).json()
    assert len(listed) == 2


def test_duplicate_overall_budget_is_rejected(client, auth):
    payload = {"year": 2026, "month": 3, "limit": "100"}
    assert client.post("/budgets", json=payload, headers=auth).status_code == 201
    assert client.post("/budgets", json=payload, headers=auth).status_code == 409


def test_duplicate_category_budget_is_rejected(client, auth, category_id):
    payload = {"year": 2026, "month": 3, "limit": "100", "category_id": category_id}
    assert client.post("/budgets", json=payload, headers=auth).status_code == 201
    assert client.post("/budgets", json=payload, headers=auth).status_code == 409


def test_invalid_month(client, auth):
    response = client.post("/budgets", json={"year": 2026, "month": 13, "limit": "1"}, headers=auth)
    assert response.status_code == 422


def test_update_and_delete_budget(client, auth):
    budget = client.post(
        "/budgets", json={"year": 2026, "month": 3, "limit": "100"}, headers=auth
    ).json()

    updated = client.patch(f"/budgets/{budget['id']}", json={"limit": "120"}, headers=auth)
    assert updated.json()["limit"] == "120.00"

    assert client.delete(f"/budgets/{budget['id']}", headers=auth).status_code == 204
    assert client.get("/budgets", headers=auth).json() == []


def test_budgets_are_private(client, auth, other_auth):
    budget = client.post(
        "/budgets", json={"year": 2026, "month": 3, "limit": "100"}, headers=auth
    ).json()
    response = client.patch(f"/budgets/{budget['id']}", json={"limit": "1"}, headers=other_auth)
    assert response.status_code == 404
