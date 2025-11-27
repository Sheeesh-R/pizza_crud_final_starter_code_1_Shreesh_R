import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

# Initialize Flask app
app = Flask(__name__)

# Database setup
DB_PATH = os.path.join('data', 'pizzas.db')

# Create data directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')

def get_db_connection():
    """Get a connection to the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create database tables if they don't exist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create Pizza table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Pizza (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
        ''')
        
        # Create Order table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "Order" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pizza_id INTEGER,
                quantity INTEGER NOT NULL,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pizza_id) REFERENCES Pizza (id)
            )
        ''')
        
        # Create PromoCode table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS PromoCode (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                discount_percent REAL NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                usage_limit INTEGER,
                times_used INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('SELECT COUNT(*) FROM Pizza')
        if cursor.fetchone()[0] == 0:
            sample_pizzas = [
                ('Margherita', 14.99),
                ('Pepperoni', 13.99),
                ('Hawaiian', 13.49),
                ('Vegetarian', 12.99),
                ('Supreme', 15.499),
                ('BBQ Chicken', 13.99),
                ('Meat Lovers', 15.99),
                ('Buffalo', 16.99)
            ]
            cursor.executemany('INSERT INTO Pizza (name, price) VALUES (?, ?)', sample_pizzas)
        
        # Add sample promo codes if table is empty
        cursor.execute('SELECT COUNT(*) FROM PromoCode')
        if cursor.fetchone()[0] == 0:
            from datetime import date, timedelta
            today = date.today()
            end_date = today + timedelta(days=365)
            
            cursor.execute('INSERT INTO PromoCode (code, discount_percent, start_date, end_date, usage_limit) VALUES (?, ?, ?, ?, ?)',
                         ('WELCOME10', 10.0, today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), None))
            cursor.execute('INSERT INTO PromoCode (code, discount_percent, start_date, end_date, usage_limit) VALUES (?, ?, ?, ?, ?)',
                         ('MIDWEEK15', 15.0, today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), 200))
            cursor.execute('INSERT INTO PromoCode (code, discount_percent, start_date, end_date, usage_limit) VALUES (?, ?, ?, ?, ?)',
                         ('FAMILY20', 20.0, today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), 150))
            conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def get_all_pizzas():
    """Get all pizzas from the database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, price FROM Pizza ORDER BY id')
        return cursor.fetchall()
    finally:
        conn.close()

def save_order(pizza_id, quantity, customer_name):
    """Save order to database and return order ID"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')  # Include microseconds (6 digits) with T separator
        cursor.execute(
            'INSERT INTO "Order" (pizza_id, quantity, customer_name, order_date) VALUES (?, ?, ?, ?)',
            (pizza_id, quantity, customer_name, current_time)
        )
        order_id = cursor.lastrowid
        conn.commit()
        return order_id
    finally:
        conn.close()

def get_order_details(order_id):
    """Get order details from database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.id, p.name, p.price, o.quantity, o.customer_name, o.order_date
            FROM "Order" o
            JOIN Pizza p ON o.pizza_id = p.id
            WHERE o.id = ?
        ''', (order_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def apply_promo_code(code, total):
    """Apply promo code discount if valid"""
    if not code:
        return 0
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT discount_percent, start_date, end_date, usage_limit, times_used
            FROM PromoCode 
            WHERE code = ?
        ''', (code.upper(),))
        promo = cursor.fetchone()
        
        if not promo:
            return 0
        
        discount_percent, start_date, end_date, usage_limit, times_used = promo
        
        # Check date validity
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        if start_date and today_str < start_date:
            return 0
        if end_date and today_str > end_date:
            return 0
        
        # Check usage limit
        if usage_limit and times_used >= usage_limit:
            return 0
        
        # Calculate discount
        discount = total * (discount_percent / 100)
        
        # Update usage count
        cursor.execute('''
            UPDATE PromoCode 
            SET times_used = times_used + 1 
            WHERE code = ?
        ''', (code.upper(),))
        conn.commit()
        
        return discount
    finally:
        conn.close()

# Routes
@app.route('/')
def menu():
    """Show the pizza menu and order form"""
    pizzas = get_all_pizzas()
    return render_template('menu.html', pizzas=pizzas)

@app.route('/order', methods=['POST'])
def create_order():
    """Process the pizza order"""
    pizza_id = request.form.get('pizza_id')
    quantity = request.form.get('quantity')
    customer_name = request.form.get('customer_name')
    promo_code = request.form.get('promo_code')
    
    if not pizza_id or not quantity or not customer_name:
        return redirect(url_for('menu'))
        
    order_id = save_order(pizza_id, quantity, customer_name)
    return redirect(url_for('confirmation', order_id=order_id, promo_code=promo_code))

@app.route('/confirmation')
def confirmation():
    """Show order confirmation"""
    order_id = request.args.get('order_id')
    promo_code = request.args.get('promo_code')
    if not order_id:
        return redirect(url_for('menu'))
        
    order = get_order_details(order_id)
    if not order:
        return redirect(url_for('menu'))
    
    total = order[2] * order[3]
    discount_amount = 0
    
    if promo_code:
        discount_amount = apply_promo_code(promo_code, total)
    
    order_data = {
        'order_id': order[0],
        'pizza_name': order[1],
        'price': order[2],
        'quantity': order[3],
        'customer_name': order[4],
        'order_date': datetime.strptime(order[5], '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%dT%H:%M:%S.%f') if 'T' in order[5] else datetime.strptime(order[5], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%dT%H:%M:%S.000000'),
        'total': total,
        'discount_amount': discount_amount,
        'final_total': total - discount_amount
    }
    
    return render_template('confirmation.html', 
                         order=order_data, 
                         display_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
