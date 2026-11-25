"""Terminal chat for the support agent."""
from agent.agent import SupportAgent
from agent.handoff import format_handoff

TAGS = {"answer": "ANSWERED", "clarify": "CLARIFYING", "handoff": "HANDED OFF"}


def main():
    agent = SupportAgent()
    session = agent.new_session()
    print("Support agent ready. Type 'quit' to exit, 'trace' to toggle the decision trace.\n")
    show_trace = False
    while True:
        try:
            msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit"}:
            break
        if msg.lower() == "trace":
            show_trace = not show_trace
            print(f"(trace {'on' if show_trace else 'off'})")
            continue
        if not msg:
            continue
        res = agent.respond(msg, session)
        print(f"\n[{TAGS[res.action]}] {res.reply}")
        if res.sources:
            print("  sources:", "; ".join(res.sources))
        if show_trace:
            print("  trace:", " > ".join(res.trace))
        if res.handoff:
            print("\n--- summary sent to human agent ---")
            print(format_handoff(res.handoff))
            print("-----------------------------------")
        print()


if __name__ == "__main__":
    main()