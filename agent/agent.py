"""Step 5: the agent loop. Decides: ANSWER, CLARIFY or HANDOFF."""
import re
from dataclasses import dataclass, field

from .retrieval import Retriever, tokenize
from .tools import extract_order_id, extract_email, lookup_order, describe_order, return_check
from .risk import check_injection, check_risk
from .handoff import build_handoff, handoff_message

COVERAGE_MIN = 0.8   # share of the question's words found in the best chunk
SCORE_MIN = 3.0      # minimum BM25 score
MAX_FAILED_LOOKUPS = 3

ORDER_WORDS = r"\b(my order|my package|my parcel|my delivery|track (my|the|this|that|it)|where is|order status|status of|has (it|my)|when will (it|my))\b"
GREETING = r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|thanks|thank you)\W*$"


@dataclass
class Result:
    action: str                      # "answer" | "clarify" | "handoff"
    reply: str
    category: str = ""
    reason: str = ""
    sources: list = field(default_factory=list)
    handoff: dict = None
    trace: list = field(default_factory=list)


class SupportAgent:
    def __init__(self):
        self.retriever = Retriever()

    def new_session(self):
        return {"order_id": None, "email": None, "verified_order": None,
                "pending_order": False, "failed": 0, "history": []}

    def respond(self, message, session=None):
        session = session if session is not None else self.new_session()
        trace = []
        res = self._decide(message.strip(), session, trace)
        res.trace = trace
        session["history"].append(("customer", message))
        session["history"].append(("agent", res.reply))
        return res

    # ---------- helpers ----------
    def _handoff(self, msg, session, category, reason, trace):
        order = session["verified_order"]
        checks = list(trace)
        h = build_handoff(msg, session, category, reason, order, checks)
        return Result("handoff", handoff_message(category), category, reason, [], h)

    def _verify(self, msg, session, trace):
        """Update session with any order id / email in the message and verify if both are known."""
        oid, em = extract_order_id(msg), extract_email(msg)
        if oid and oid != session["order_id"]:
            session["verified_order"] = None
        if oid:
            session["order_id"] = oid
        if em:
            session["email"] = em
        if (oid or em) and session["order_id"] and session["email"]:
            status, order = lookup_order(session["order_id"], session["email"])
            if status == "ok":
                session["verified_order"] = order
                trace.append(f"identity: verified {order['order_id']}")
            else:
                session["verified_order"] = None
                session["failed"] += 1
                trace.append(f"identity: no match (attempt {session['failed']})")
            return status
        return None

    # ---------- main decision ----------
    def _decide(self, msg, session, trace):
        # 1. safety
        reason = check_injection(msg)
        if reason:
            trace.append("safety: injection pattern matched")
            return self._handoff(msg, session, "security", reason, trace)
        trace.append("safety: pass")

        # 2. identity (silent, so a later handoff can carry verified order details)
        verify_status = self._verify(msg, session, trace)
        if session["failed"] >= MAX_FAILED_LOOKUPS:
            return self._handoff(msg, session, "verification_failed", "Too many failed order verifications", trace)

        # 3. risk
        risk = check_risk(msg)
        if risk:
            category, priority, reason = risk
            trace.append(f"risk: {category} ({priority})")
            return self._handoff(msg, session, category, reason, trace)
        trace.append("risk: pass")

        # 4. greeting / empty
        if re.match(GREETING, msg, re.IGNORECASE) or not tokenize(msg):
            return Result("clarify", "Hi! I can help with order status, returns, shipping, warranty, payments and product questions. What do you need?")

        # 5. order question
        em_given = extract_email(msg)
        follow_up = (session["verified_order"] is not None
                     and re.search(r"\b(it|this order|that order)\b", msg, re.IGNORECASE)
                     and re.search(r"\b(return|send back|arrive|ship\w*|deliver\w*)\b", msg, re.IGNORECASE))
        is_order = (re.search(ORDER_WORDS, msg, re.IGNORECASE) or extract_order_id(msg)
                    or (session["pending_order"] and em_given) or follow_up)
        if is_order:
            trace.append("intent: order")
            order = session["verified_order"]
            if order is None:
                session["pending_order"] = True
                if verify_status == "no_match":
                    reply = ("I couldn't find an order matching those details. "
                             "Please double-check the order number and the email used at checkout.")
                elif not session["order_id"] and not session["email"]:
                    reply = "Happy to check. What is your order number (like ORD-1234) and the email you used at checkout?"
                elif not session["email"]:
                    reply = "Thanks. What email address did you use at checkout? I need it to verify the order."
                else:
                    reply = "Thanks. What is your order number (like ORD-1234)?"
                return Result("clarify", reply)
            session["pending_order"] = False
            text = describe_order(order)
            if text is None:
                return self._handoff(msg, session, "unknown_status", "Order has a status the agent does not recognise", trace)
            if re.search(r"\b(return|send back|refund)\b", msg, re.IGNORECASE):
                rc = return_check(order)
                if rc["checked"]:
                    if rc["within_window"]:
                        text += f" It was delivered {rc['days_since_delivery']} days ago, so it is inside our {rc['window_days']}-day return window."
                    else:
                        text += f" It was delivered {rc['days_since_delivery']} days ago, which is outside our {rc['window_days']}-day return window, so it is not eligible for a standard return."
                else:
                    text += " Returns are only possible after an order has been delivered."
            return Result("answer", text, sources=[f"Order database: {order['order_id']}"])

        # 6. policy / product question
        trace.append("intent: policy/product")
        hits = self.retriever.search(msg, k=2)
        if not hits:
            trace.append("retrieval: no matching chunk")
            return self._handoff(msg, session, "low_confidence", "No policy or product text matched the question", trace)
        top = hits[0]
        trace.append(f"retrieval: top score={top['score']:.2f} coverage={top['coverage']:.2f} [{top['chunk']['source']}]")
        unknown = self.retriever.unknown_terms(msg)
        if unknown:
            trace.append(f"retrieval: unfamiliar terms {unknown}")
            return self._handoff(msg, session, "low_confidence",
                                 f"Question uses terms not found in our policies: {', '.join(unknown)}", trace)
        if top["coverage"] < COVERAGE_MIN or top["score"] < SCORE_MIN:
            return self._handoff(msg, session, "low_confidence",
                                 f"Weak match (score {top['score']:.2f}, coverage {top['coverage']:.2f})", trace)
        used = [top]
        if len(hits) > 1 and hits[1]["coverage"] >= COVERAGE_MIN and hits[1]["score"] >= 0.7 * top["score"]:
            used.append(hits[1])
        reply = " ".join(h["chunk"]["text"] for h in used)
        return Result("answer", reply, sources=[h["chunk"]["source"] for h in used])