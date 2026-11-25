"""Step 3: order lookup tool with an identity check."""
import os
import re
import sqlite3
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "data", "store.db")

RETURN_WINDOW_DAYS = 30


def today():
    """Fixed date by default so eval results are reproducible. Override with AGENT_TODAY=YYYY-MM-DD."""
    return date.fromisoformat(os.environ.get("AGENT_TODAY", "2026-11-25"))


def extract_order_id(text):
    m = re.search(r"\bORD-\d{4}\b", text, re.IGNORECASE)
    return m.group(0).upper() if m else None


def extract_email(text):
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return m.group(0).lower() if m else None


def lookup_order(order_id, email):
    """Return (status, order). status is 'missing_info', 'no_match' or 'ok'.

    'no_match' is used BOTH when the order id does not exist AND when the
    email does not belong to it, so an attacker cannot tell which order ids exist.
    """
    if not order_id or not email:
        return "missing_info", None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    if row is None or row["email"].lower() != email.strip().lower():
        return "no_match", None
    return "ok", dict(row)


def describe_order(o):
    """Build the answer straight from the database row, with no guessing."""
    s = o["status"]
    head = f"Order {o['order_id']} ({o['items']})"
    if s == "processing":
        return f"{head} is being prepared and has not shipped yet. Estimated delivery: {o['eta']}."
    if s == "shipped":
        return (f"{head} has shipped with {o['carrier']} (tracking {o['tracking']}). "
                f"Estimated delivery: {o['eta']}.")
    if s == "delivered":
        return f"{head} was delivered on {o['delivered']}."
    if s == "cancelled":
        return f"{head} was cancelled."
    if s == "return_received":
        return (f"{head}: we have received your returned item. "
                f"Refund status is handled by our human support team.")
    return None  # unknown status -> the agent should hand off


def return_check(o):
    """Is a delivered order still inside the return window?"""
    if o["status"] != "delivered" or not o["delivered"]:
        return {"checked": False, "reason": "order is not delivered"}
    days = (today() - date.fromisoformat(o["delivered"])).days
    return {"checked": True, "days_since_delivery": days,
            "window_days": RETURN_WINDOW_DAYS, "within_window": days <= RETURN_WINDOW_DAYS}


if __name__ == "__main__":
    tests = [
        ("ORD-1002", "maya@example.com"),
        ("ORD-1002", "MAYA@example.com"),
        ("ORD-1002", "li@example.com"),
        ("ORD-9999", "maya@example.com"),
        ("ORD-1002", None),
        ("ORD-1002' OR '1'='1", "maya@example.com"),
        ("ORD-1008", "li@example.com"),
        ("ORD-1001", "maya@example.com"),
    ]
    for oid, em in tests:
        status, order = lookup_order(oid, em)
        print(f"{oid!r:28} {em!r:22} -> {status}")
        if order:
            print("    ", describe_order(order))
            print("    ", return_check(order))