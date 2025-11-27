import sqlite3
import os

DB_PATH = os.path.join('data', 'pizzas.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# First check current orders
cursor.execute('SELECT id, customer_name, pizza_id, quantity FROM "Order" ORDER BY id')
orders = cursor.fetchall()
print('Current orders:')
for order in orders:
    print(f'  ID: {order[0]}, Customer: {order[1]}, Pizza ID: {order[2]}, Qty: {order[3]}')

# Delete all orders except ID 1
cursor.execute('DELETE FROM "Order" WHERE id != 1')
deleted_count = cursor.rowcount
conn.commit()

print(f'Deleted {deleted_count} orders (kept order ID 1)')

# Show remaining orders
cursor.execute('SELECT id, customer_name, pizza_id, quantity FROM "Order" ORDER BY id')
remaining_orders = cursor.fetchall()
print('Remaining orders:')
for order in remaining_orders:
    print(f'  ID: {order[0]}, Customer: {order[1]}, Pizza ID: {order[2]}, Qty: {order[3]}')

conn.close()
