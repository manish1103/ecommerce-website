import pytest
import sqlite3
from app import app, init_db

# ✅ Setup: Temporary Test Database
@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_database.db"
    app.config["DATABASE"] = str(db_path)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # Reinitialize DB
    with app.app_context():
        init_db()

    client = app.test_client()
    yield client


# 🧠 Helper: Insert a demo product for cart/checkout tests
def add_test_product(db_path="database.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO products (name, category, price, image, description)
        VALUES ('Test Product', 'Electronics', 499.0, 'images/test.jpg', 'A test item for automation.')
    """)
    conn.commit()
    conn.close()


# ✅ TEST 1: User Signup Flow
def test_user_signup(client):
    response = client.post("/signup", data={
        "name": "Manish Tester",
        "email": "testuser@example.com",
        "password": "12345"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Account created" in response.data or b"successfully" in response.data



# ✅ TEST 2: Login Flow
def test_user_login(client):
    client.post("/signup", data={
        "name": "Manish Tester",
        "email": "loginuser@example.com",
        "password": "testpass"
    })
    response = client.post("/login", data={
        "email": "loginuser@example.com",
        "password": "testpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data or b"Login successful" in response.data


# ✅ TEST 3: Add to Cart + View Cart
def test_cart_flow(client):
    add_test_product()
    response = client.get("/add_to_cart/1", follow_redirects=True)
    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "Item added to cart" in text or "🛒" in text

    cart_page = client.get("/cart")
    assert cart_page.status_code == 200
    assert b"Test Product" in cart_page.data


# ✅ TEST 4: Checkout Flow (POST)
def test_checkout_flow(client):
    add_test_product()
    client.get("/add_to_cart/1", follow_redirects=True)
    response = client.post("/checkout", data={
        "name": "Test Buyer",
        "email": "buyer@example.com",
        "address": "Jhansi",
        "payment_method": "UPI",
        "total": "499"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Order" in response.data or b"Success" in response.data


# ✅ TEST 5: Admin Login and Dashboard
def test_admin_login_and_dashboard(client):
    response = client.post("/admin_login", data={
        "username": "admin",
        "password": "1234"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Dashboard" in response.data or b"Orders" in response.data
