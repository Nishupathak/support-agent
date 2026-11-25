"""Step 6: the package a human agent receives when the bot hands off."""

PRIORITY = {
    "legal_safety": "urgent", "fraud_payment": "high", "anger": "high",
    "verification_failed": "high", "explicit_human": "normal",
    "action_request": "normal", "low_confidence": "normal",
    "unknown_status": "normal", "security": "low",
}

CUSTOMER_MESSAGES = {
    "legal_safety": "I'm sorry to hear that. This needs a person right away, so I'm escalating it to our support team as urgent.",
    "fraud_payment": "Payment and fraud issues need a human to review them securely, so I'm passing this to our support team. Please don't share full card numbers in chat.",
    "anger": "I'm sorry about this experience. I'm handing you over to a human agent who can look into it properly.",
    "action_request": "I can't process refunds, cancellations, returns or address changes myself, so I'm passing this to a human agent who can.",
    "explicit_human": "Of course, I'm connecting you with a human agent.",
    "security": "I can't help with that request. If you have a question about an order or our policies I'm happy to help, and I've flagged this conversation for our team.",
    "low_confidence": "I'm not confident I can answer that correctly from our policies, so I'm passing it to a human agent rather than guessing.",
    "verification_failed": "I couldn't verify those order details after several tries, so I'm passing this to a human agent who can help securely.",
    "unknown_status": "I can't read the status of that order reliably, so I'm passing it to a human agent.",
}
FOOTER = " They will see this conversation, so you won't need to repeat yourself. Human support hours: Monday to Friday, 9 AM to 6 PM Eastern Time."


def handoff_message(category):
    return CUSTOMER_MESSAGES[category] + FOOTER


def build_handoff(message, session, category, reason, order=None, checks=None):
    summary = None
    if order:
        summary = {k: order[k] for k in
                   ("order_id", "name", "email", "status", "items", "total", "placed", "shipped", "delivered", "carrier", "tracking", "eta")}
    return {
        "priority": PRIORITY.get(category, "normal"),
        "category": category,
        "reason": reason,
        "customer_message": message,
        "identity_verified": order is not None,
        "claimed_order_id": session.get("order_id"),
        "order": summary,
        "agent_checked": checks or [],
        "transcript": list(session["history"][-6:]) + [("customer", message)],
    }


def format_handoff(h):
    lines = [f"HANDOFF [{h['priority'].upper()}] {h['category']}", f"Reason: {h['reason']}",
             f"Customer said: {h['customer_message']}"]
    if h["order"]:
        o = h["order"]
        lines.append(f"Verified order: {o['order_id']} | {o['status']} | {o['items']} | ${o['total']:.2f} | {o['name']} <{o['email']}>")
    elif h["claimed_order_id"]:
        lines.append(f"Customer mentioned {h['claimed_order_id']} but identity is NOT verified")
    else:
        lines.append("No order identified")
    lines.append("Agent already checked: " + ("; ".join(h["agent_checked"]) or "nothing"))
    return "\n".join(lines)