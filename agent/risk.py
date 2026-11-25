"""Step 4: safety and risk rules. Plain regex, so every decision is explainable."""
import re

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the |previous |prior |above |these )*(instructions|rules|polic\w+|guidelines)",
    r"disregard .*(instructions|rules|polic\w+)",
    r"forget (everything|your|all|the rules)",
    r"(reveal|show|print|repeat|tell me) .*(system prompt|your instructions|your prompt)",
    r"system prompt",
    r"developer mode|jailbreak",
    r"override (the |your )?(rules|polic\w+|limit|approval|checks?)",
    r"\bi am (the |an? |your )?(admin|administrator|manager|owner|developer|ceo|engineer)\b",
    r"\byou are now\b|\bpretend (to be|you are)\b|\bnew instructions\b",
]

# (category, priority, regex, reason). Checked in order, first match wins.
RISK_RULES = [
    ("legal_safety", "urgent",
     r"\b(lawyer|attorney|sue|suing|lawsuit|legal action|court|police|injur\w*|hospital|burned|burnt|caught fire|on fire|smoke|exploded|electric shock|allergic reaction)\b",
     "Legal threat or safety incident"),
    ("fraud_payment", "high",
     r"\b(fraud\w*|scam\w*|unauthori[sz]ed|stolen|hacked|chargeback|charged (me )?(twice|two times|again)|double[- ]charg\w*|dispute|overcharg\w*|wrong charge)\b",
     "Payment problem, fraud or dispute"),
    ("anger", "high",
     r"\b(furious|angry|outrageous|unacceptable|ridiculous|disgusting|worst|terrible|awful|useless|pathetic|rip[- ]?off|sick of|never (shopping|buying|ordering) (here )?again)\b",
     "Customer is very upset"),
    ("explicit_human", "normal",
     r"\b(human|real person|live agent|representative|supervisor|complain\w*|(speak|talk) to (a |an |the )?(manager|agent|person|someone))\b",
     "Customer asked for a human"),
    ("action_request", "normal",
     r"\b(want|need|would like|like) (a |to get a |to have a )?refund\b|\brefund (me|my|this|it|the order)\b|\b(get|issue|process) (me )?(a )?refund\b|\bmoney back\b"
     r"|\bcancel (my|the|this) order\b|\b(change|update|edit) (my|the) (shipping )?address\b|\b(start|initiate|process|make) (a |my )?return\b",
     "Customer wants an action the agent cannot perform (refund, cancel, change address, start a return)"),
]


def check_injection(text):
    t = text.lower()
    for p in INJECTION_PATTERNS:
        if re.search(p, t):
            return "Possible prompt injection or social engineering"
    return None


def _shouting(text):
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 15 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return True
    return "!!!" in text


def check_risk(text):
    """Return (category, priority, reason) or None."""
    t = text.lower()
    for category, priority, pattern, reason in RISK_RULES:
        if re.search(pattern, t):
            return category, priority, reason
    if _shouting(text):
        return "anger", "high", "Customer is shouting / very upset"
    return None