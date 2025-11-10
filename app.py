from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ================= DATABASE SETUP =================
def init_db():
    with sqlite3.connect("database.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                price REAL,
                image TEXT,
                description TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                email TEXT,
                address TEXT,
                payment_method TEXT,
                total REAL,
                status TEXT DEFAULT 'Pending'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER
            )
        """)

    
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ✅ Default admin
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE username='admin'")
        if not cur.fetchone():
            conn.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ("admin", "1234"))
            conn.commit()

    print("✅ Database initialized successfully (with all tables)")

init_db()

# ================= HOME + SEARCH + CATEGORY =================
@app.route('/', methods=['GET'])
def home():
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT category FROM products")
    categories = [row['category'] for row in cur.fetchall()]

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search_query:
        query += " AND name LIKE ?"
        params.append(f"%{search_query}%")
    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cur.execute(query, params)
    products = cur.fetchall()
    conn.close()

    return render_template("index.html", products=products, categories=categories,
                           selected_category=category_filter, search_query=search_query)

# ================= PRODUCT DETAIL =================
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Main product
    cur.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()

    if not product:
        return "Product Not Found", 404

    # Related products (same category)
    cur.execute("SELECT * FROM products WHERE category=? AND id!=? LIMIT 4", (product['category'], product_id))
    related_products = cur.fetchall()

    conn.close()
    return render_template("product.html", product=product, related_products=related_products)


# ================= CATEGORY PAGE =================
@app.route('/category')
def all_categories():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # सभी unique categories निकालना
    cur.execute("SELECT DISTINCT category FROM products")
    categories = [row['category'] for row in cur.fetchall()]

    # सभी products लाना
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    conn.close()

    return render_template("category.html", products=products, categories=categories)


# ================= ADD TO CART =================
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', [])
    cart.append(product_id)
    session['cart'] = cart
    flash("🛒 Item added to cart successfully!")
    return redirect(url_for('cart'))

# ================= VIEW CART =================
@app.route('/cart')
def cart():
    cart = session.get('cart', [])
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    products, total = [], 0
    if cart:
        placeholders = ','.join('?' * len(cart))
        cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
        products = cur.fetchall()
        total = sum([p['price'] for p in products])
    conn.close()
    return render_template("cart.html", products=products, total=total)
    
# ================= REMOVE FROM CART =================
@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    if product_id in cart:
        cart.remove(product_id)
    session['cart'] = cart
    flash("❌ Item removed from cart.")
    return redirect(url_for('cart'))



# ================= CHECKOUT =================
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        flash("Your cart is empty!")
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        payment_method = request.form['payment_method']
        total = request.form['total']
        user_id = session.get('user_id', None)

        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO orders (user_id, name, email, address, payment_method, total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, name, email, address, payment_method, total))
            conn.commit()

        session.pop('cart', None)
        return render_template("order_success.html", name=name)

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    placeholders = ','.join('?' * len(cart))
    cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
    products = cur.fetchall()
    total = sum([p['price'] for p in products])
    conn.close()
    return render_template("checkout.html", products=products, total=total)

# ================= USER SIGNUP / LOGIN =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        with sqlite3.connect("database.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=?", (email,))
            if cur.fetchone():
                flash("⚠️ Email already registered!")
                return redirect(url_for('signup'))
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
            flash("✅ Account created! Please login.")
        return redirect(url_for('login'))
    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            user = cur.fetchone()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash(f"👋 Welcome, {user['name']}!")
            return redirect(url_for('dashboard'))
        flash("❌ Invalid credentials!")
    return render_template("login.html")

@app.route('/user_logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("👋 You’ve logged out successfully!")
    return redirect(url_for('home'))

# ================= USER DASHBOARD + WISHLIST =================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    cur.execute("SELECT * FROM orders WHERE user_id=?", (user_id,))
    orders = cur.fetchall()
    cur.execute("""
        SELECT w.id, p.name, p.price, p.image 
        FROM wishlist w
        JOIN products p ON w.product_id = p.id
        WHERE w.user_id=?
    """, (user_id,))
    wishlist = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", user=user, orders=orders, wishlist=wishlist)

@app.route('/add_to_wishlist/<int:product_id>')
def add_to_wishlist(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    with sqlite3.connect("database.db") as conn:
        conn.execute("INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        conn.commit()
    flash("❤️ Added to Wishlist!")
    return redirect(url_for('dashboard'))

@app.route('/remove_wishlist/<int:wishlist_id>')
def remove_wishlist(wishlist_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect("database.db") as conn:
        conn.execute("DELETE FROM wishlist WHERE id=?", (wishlist_id,))
        conn.commit()
    flash("❌ Removed from Wishlist!")
    return redirect(url_for('dashboard'))

# ================= CONTACT PAGE =================
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)",
                         (name, email, message))
            conn.commit()
        flash("✅ Message sent successfully! Thank you for contacting us.")
        return redirect(url_for('contact'))

    return render_template("contact.html")


# ================= ADMIN LOGIN =================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("database.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
            admin = cur.fetchone()
        if admin:
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template("admin_login.html", error="Invalid Credentials")
    return render_template("admin_login.html")

# ================= ADMIN DASHBOARD =================
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()
    conn.close()
    return render_template("admin_dashboard.html", products=products, orders=orders)
    
    # ================= ADMIN VIEW CONTACTS =================
@app.route('/admin_contacts')
def admin_contacts():
    # 🔒 Ensure only logged-in admin can access this page
    if 'admin' not in session:
        flash("⚠️ Please login as admin to access contact messages.")
        return redirect(url_for('admin_login'))

    # ✅ Fetch all contact messages from DB
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM contact_messages ORDER BY id DESC")
    messages = cur.fetchall()
    conn.close()

    # ✅ Render the admin contacts template
    return render_template("admin_contacts.html", messages=messages)
    
    # ================= USER LOGOUT =================
@app.route('/logout_user')
def logout_user():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("👋 You’ve logged out successfully!")
    return redirect(url_for('home'))



# ================= RUN APP =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
