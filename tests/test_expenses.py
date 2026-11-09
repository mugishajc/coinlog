def add(client, headers, amount, spent_on="2026-03-10", **extra):
    payload = {"amount": amount, "spent_on": spent_on, **extra}
    response = client.post("/expenses", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_fetch_expense(client, auth, category_id):
    created = add(client, auth, "12.50", description="Lunch", category_id=category_id)
    assert created["amount"] == "12.50"

    fetched = client.get(f"/expenses/{created['id']}", headers=auth).json()
    assert fetched["description"] == "Lunch"
    assert fetched["category_id"] == category_id


def test_amount_must_be_positive_with_two_decimals(client, auth):
    for bad in ["0", "-5", "1.234"]:
        response = client.post(
            "/expenses", json={"amount": bad, "spent_on": "2026-03-01"}, headers=auth
        )
        assert response.status_code == 422, bad


def test_cannot_use_someone_elses_category(client, auth, other_auth):
    foreign = client.get("/categories", headers=other_auth).json()[0]["id"]
    response = client.post(
        "/expenses",
        json={"amount": "5", "spent_on": "2026-03-01", "category_id": foreign},
        headers=auth,
    )
    assert response.status_code == 404


def test_users_cannot_see_each_others_expenses(client, auth, other_auth):
    mine = add(client, auth, "9.99")
    assert client.get(f"/expenses/{mine['id']}", headers=other_auth).status_code == 404
    assert client.delete(f"/expenses/{mine['id']}", headers=other_auth).status_code == 404
    assert client.get("/expenses", headers=other_auth).json()["total"] == 0


def test_list_filters(client, auth, category_id):
    add(client, auth, "5.00", "2026-03-01", description="Bus ticket")
    add(client, auth, "40.00", "2026-03-15", description="Groceries", category_id=category_id)
    add(client, auth, "80.00", "2026-04-02", description="Dinner out", category_id=category_id)

    def amounts(**params):
        page = client.get("/expenses", params=params, headers=auth).json()
        return [item["amount"] for item in page["items"]]

    assert amounts(date_from="2026-03-01", date_to="2026-03-31") == ["40.00", "5.00"]
    assert amounts(category_id=category_id) == ["80.00", "40.00"]
    assert amounts(uncategorized=True) == ["5.00"]
    assert amounts(min_amount="10", max_amount="50") == ["40.00"]
    assert amounts(q="dinner") == ["80.00"]


def test_pagination(client, auth):
    for day in range(1, 8):
        add(client, auth, "1.00", f"2026-05-{day:02d}")

    page = client.get("/expenses", params={"limit": 3, "offset": 3}, headers=auth).json()

    assert page["total"] == 7
    assert [item["spent_on"] for item in page["items"]] == [
        "2026-05-04",
        "2026-05-03",
        "2026-05-02",
    ]


def test_partial_update(client, auth, category_id):
    expense = add(client, auth, "10.00", description="Taxi")
    response = client.patch(
        f"/expenses/{expense['id']}",
        json={"amount": "11.25", "category_id": category_id},
        headers=auth,
    )
    body = response.json()
    assert body["amount"] == "11.25"
    assert body["category_id"] == category_id
    assert body["description"] == "Taxi"


def test_delete_expense(client, auth):
    expense = add(client, auth, "3.00")
    assert client.delete(f"/expenses/{expense['id']}", headers=auth).status_code == 204
    assert client.get(f"/expenses/{expense['id']}", headers=auth).status_code == 404


def test_deleting_category_keeps_its_expenses(client, auth, category_id):
    expense = add(client, auth, "7.00", category_id=category_id)
    assert client.delete(f"/categories/{category_id}", headers=auth).status_code == 204
    assert client.get(f"/expenses/{expense['id']}", headers=auth).json()["category_id"] is None


def test_category_names_are_unique_per_user(client, auth, other_auth):
    assert client.post("/categories", json={"name": "food"}, headers=auth).status_code == 409
    assert client.post("/categories", json={"name": "Pets"}, headers=auth).status_code == 201
    # Another user can have the same name.
    assert client.post("/categories", json={"name": "Pets"}, headers=other_auth).status_code == 201


def test_category_color_must_be_hex(client, auth):
    bad = client.post("/categories", json={"name": "Gym", "color": "red"}, headers=auth)
    good = client.post("/categories", json={"name": "Gym", "color": "#1a2B3c"}, headers=auth)
    assert bad.status_code == 422
    assert good.status_code == 201
