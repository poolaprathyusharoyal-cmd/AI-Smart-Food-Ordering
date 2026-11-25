def test_catalog_is_public_and_filters(client):
    response = client.get("/api/menu_items", params={"vegetarian": True, "max_price": 100})
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Masala Dosa"]


def test_catalog_management_is_admin_only(client):
    payload = {"name": "Lemon Rice", "description": "Bright and savory", "category": "Lunch", "is_vegetarian": True, "price": "110.00", "portions": 8}
    denied = client.post("/api/menu_items", auth=("customer1", "Customer123!"), json=payload)
    assert denied.status_code == 403
    created = client.post("/api/menu_items", auth=("admin", "Admin123!"), json=payload)
    assert created.status_code == 201
    assert created.json()["price"] == "110.00"


def test_catalog_rejects_nonpositive_price(client):
    payload = {"name": "Bad Price", "description": "Nope", "category": "Lunch", "is_vegetarian": True, "price": "0", "portions": 2}
    assert client.post("/api/menu_items", auth=("admin", "Admin123!"), json=payload).status_code == 422


def test_catalog_update_and_soft_delete(client):
    auth = ("admin", "Admin123!")
    item = client.get("/api/menu_items", params={"keyword": "Masala Dosa"}).json()[0]
    updated = {"name": item["name"], "description": "Updated recipe", "category": item["category"], "is_vegetarian": True, "price": "95.00", "portions": item["portions"]}
    response = client.put(f"/api/menu_items/{item['id']}", auth=auth, json=updated)
    assert response.status_code == 200 and response.json()["price"] == "95.00"
    assert client.delete(f"/api/menu_items/{item['id']}", auth=auth).status_code == 204
    assert client.get(f"/api/menu_items/{item['id']}").status_code == 404
