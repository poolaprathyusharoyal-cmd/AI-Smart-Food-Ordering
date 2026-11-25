from concurrent.futures import ThreadPoolExecutor


def test_order_uses_catalog_price_and_idempotency(client):
    item = client.get("/api/menu_items", params={"keyword": "Masala Dosa"}).json()[0]
    data = {"lines": [{"item_id": item["id"], "quantity": 1}]}
    first = client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": "order-key-one"}, json=data)
    replay = client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": "order-key-one"}, json=data)
    assert first.status_code == 201
    assert first.json()["total"] == "90.00"
    assert replay.json()["id"] == first.json()["id"]
    mismatch = client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": "order-key-one"}, json={"lines": [{"item_id": 2, "quantity": 1}]})
    assert mismatch.status_code == 409


def test_invalid_quantity_and_other_users_order_are_rejected(client):
    item = client.get("/api/menu_items").json()[0]
    invalid = client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": "bad-qty"}, json={"lines": [{"item_id": item["id"], "quantity": 11}]})
    assert invalid.status_code == 422
    created = client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": "ownership-check"}, json={"lines": [{"item_id": item["id"], "quantity": 1}]})
    hidden = client.get(f"/api/orders/{created.json()['id']}", auth=("customer2", "Customer123!"))
    assert hidden.status_code == 404


def test_cancellation_restores_inventory_once(client):
    auth = ("customer1", "Customer123!")
    item = client.get("/api/menu_items", params={"keyword": "Masala Dosa"}).json()[0]
    before = item["portions"]
    created = client.post("/api/orders", auth=auth, headers={"Idempotency-Key": "cancel-once"}, json={"lines": [{"item_id": item["id"], "quantity": 1}]})
    order_id = created.json()["id"]
    assert client.post(f"/api/orders/{order_id}/cancel", auth=auth).status_code == 200
    assert client.post(f"/api/orders/{order_id}/cancel", auth=auth).status_code == 409
    assert client.get(f"/api/menu_items/{item['id']}").json()["portions"] == before


def test_order_in_preparation_cannot_be_cancelled(client):
    auth = ("customer1", "Customer123!")
    item = client.get("/api/menu_items", params={"keyword": "Masala Dosa"}).json()[0]
    created = client.post("/api/orders", auth=auth, headers={"Idempotency-Key": "preparing-order"}, json={"lines": [{"item_id": item["id"], "quantity": 1}]})
    order_id = created.json()["id"]
    denied = client.patch(f"/api/admin/orders/{order_id}/status", auth=auth, json={"status": "PREPARING"})
    assert denied.status_code == 403
    started = client.patch(f"/api/admin/orders/{order_id}/status", auth=("admin", "Admin123!"), json={"status": "PREPARING"})
    assert started.status_code == 200
    assert client.post(f"/api/orders/{order_id}/cancel", auth=auth).status_code == 409


def test_only_one_concurrent_order_can_claim_last_portion(client):
    item = client.get("/api/menu_items", params={"keyword": "Test Chicken"}).json()[0]
    def create(key):
        return client.post("/api/orders", auth=("customer1", "Customer123!"), headers={"Idempotency-Key": key}, json={"lines": [{"item_id": item["id"], "quantity": 1}]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, ["race-one", "race-two"]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert client.get(f"/api/menu_items/{item['id']}").json()["portions"] == 0
