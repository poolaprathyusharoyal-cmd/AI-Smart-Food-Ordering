def test_basic_auth_and_role_checks(client):
    assert client.get("/api/me", auth=("nobody", "wrong")).status_code == 401
    assert client.get("/api/me", auth=("customer1", "Customer123!")).json()["role"] == "customer"
    payload = {"name": "Admin Dish", "description": "A dish", "category": "Lunch", "is_vegetarian": True, "price": "100.00", "portions": 1}
    assert client.post("/api/menu_items", auth=("customer1", "Customer123!"), json=payload).status_code == 403
