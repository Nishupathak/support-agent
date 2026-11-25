"""Creates data/store.db with products and orders (fake demo data)."""
import sqlite3
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "store.db")

# name, description, price, stock, warranty
PRODUCTS = [
    ("AirPulse Wireless Earbuds", "Bluetooth 5.3 earbuds with active noise cancellation and 24 hour battery life with the case.", 79.0, 120, "1 year"),
    ("VoltCharge 65W Charger", "Compact 65 watt USB-C fast charger with two ports. Works with laptops and phones.", 39.0, 300, "90 days"),
    ("TrailMate Smartwatch", "Smartwatch with heart rate tracking, GPS and 7 day battery life. Water resistant to 50 metres.", 149.0, 45, "1 year"),
    ("SnapDesk Laptop Stand", "Aluminium adjustable laptop stand, fits laptops from 11 to 17 inches.", 29.0, 0, "90 days"),
    ("PixelView 27 inch Monitor", "27 inch 4K IPS monitor with USB-C input and 60 Hz refresh rate.", 329.0, 18, "1 year"),
    ("CloudFit Desk Mat", "Large 90 by 40 centimetre water resistant desk mat. Final sale clearance item.", 15.0, 60, "none"),
]

N = None  # short for "no value"

# order_id, email, name, status, placed, shipped, delivered, carrier, tracking, eta, total, items
ORDERS = [
    ("ORD-1001", "maya@example.com", "Maya Rao", "delivered", "2026-11-01", "2026-11-02", "2026-11-05", "UPS", "1Z999AA10123456784", N, 79.0, "AirPulse Wireless Earbuds"),
    ("ORD-1002", "maya@example.com", "Maya Rao", "shipped", "2026-11-21", "2026-11-22", N, "FedEx", "794644790132", "2026-11-27", 118.0, "VoltCharge 65W Charger; AirPulse Wireless Earbuds"),
    ("ORD-1003", "li@example.com", "Li Wei", "processing", "2026-11-25", N, N, N, N, "2026-11-30", 329.0, "PixelView 27 inch Monitor"),
    ("ORD-1004", "sam@example.com", "Sam Carter", "cancelled", "2026-11-10", N, N, N, N, N, 29.0, "SnapDesk Laptop Stand"),
    ("ORD-1005", "sam@example.com", "Sam Carter", "delivered", "2026-10-15", "2026-10-16", "2026-10-19", "UPS", "1Z999AA10987654321", N, 149.0, "TrailMate Smartwatch"),
    ("ORD-1006", "ana@example.com", "Ana Lopez", "return_received", "2026-11-02", "2026-11-03", "2026-11-06", "USPS", "9400111899223100001", N, 39.0, "VoltCharge 65W Charger"),
    ("ORD-1007", "raj@example.com", "Raj Patel", "shipped", "2026-11-23", "2026-11-24", N, "DHL", "JD014600003SE", "2026-11-28", 15.0, "CloudFit Desk Mat"),
    ("ORD-1008", "li@example.com", "Li Wei", "delivered", "2026-09-20", "2026-09-21", "2026-09-24", "FedEx", "794644790999", N, 79.0, "AirPulse Wireless Earbuds"),
]


def build():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.execute(
        "CREATE TABLE products(name TEXT, description TEXT, price REAL, stock INT, warranty TEXT)"
    )
    conn.execute(
        """CREATE TABLE orders(
            order_id TEXT PRIMARY KEY, email TEXT, name TEXT, status TEXT,
            placed TEXT, shipped TEXT, delivered TEXT, carrier TEXT,
            tracking TEXT, eta TEXT, total REAL, items TEXT)"""
    )
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ORDERS)
    conn.commit()
    conn.close()
    print("built", DB)


if __name__ == "__main__":
    build()