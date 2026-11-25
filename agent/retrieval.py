"""Step 2: BM25 retrieval over policy bullets and product rows."""
import math
import os
import re
import sqlite3
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
POLICY_PATH = os.path.join(DATA, "policies.md")
DB_PATH = os.path.join(DATA, "store.db")

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "i", "you",
    "we", "my", "your", "our", "can", "to", "of", "for", "in", "on", "it", "and",
    "or", "if", "me", "what", "how", "when", "which", "that", "this", "be", "have",
    "has", "with", "there", "any", "about", "at", "by", "from", "will", "would",
    # generic words that say nothing about the topic
    "policy", "policies", "take", "takes", "offer", "possible", "get", "please",
    "tell", "know", "use", "give", "let", "also", "just", "many",
}

# Customer word -> words the policy uses for the same idea. Applied to the query only.
SYNONYMS = {
    "window": ["within", "day"],
    "long": ["within", "day", "business"],
    "bitcoin": ["cryptocurrency"], "crypto": ["cryptocurrency"], "ethereum": ["cryptocurrency"],
    "cost": ["usd"], "price": ["usd"], "dollar": ["usd"], "much": ["usd"],
    "need": ["require"], "must": ["require"],
    "size": ["inch"],
}
for _country in ["india", "uk", "europe", "australia", "china", "japan", "germany", "france",
                 "mexico", "brazil", "overseas", "abroad", "worldwide", "global", "outside"]:
    SYNONYMS[_country] = ["international"]


def stem(word):
    """Very light stemmer: ing / ed / plural s, then undo doubled consonants (shipp -> ship)."""
    if len(word) > 7 and word.endswith("able"):
        word = word[:-4]
    elif len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    return word


def tokenize(text):
    """Lowercase, split into words, drop stopwords, stem."""
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]


def load_policy_chunks():
    """One chunk per bullet. Each chunk remembers its section heading."""
    chunks = []
    section = ""
    with open(POLICY_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## "):
                section = line[3:]
            elif line.startswith("- "):
                chunks.append({
                    "id": f"policy:{section}:{len(chunks)}",
                    "source": f"Policy - {section}",
                    "text": line[2:],
                    "index_text": f"{section}. {line[2:]}",
                })
    return chunks


def load_product_chunks():
    """One chunk per product row."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT name, description, price, stock, warranty FROM products").fetchall()
    conn.close()
    chunks = []
    for name, desc, price, stock, warranty in rows:
        availability = "In stock" if stock > 0 else "Out of stock"
        text = f"{name}: {desc} Price {price:.0f} USD. Warranty: {warranty}. {availability}."
        chunks.append({
            "id": f"product:{name}",
            "source": f"Product - {name}",
            "text": text,
            "index_text": text,
        })
    return chunks


class BM25:
    def __init__(self, token_lists, k1=1.5, b=0.75):
        self.docs = token_lists
        self.k1, self.b = k1, b
        self.n = len(token_lists)
        self.avg_len = sum(len(d) for d in token_lists) / self.n
        self.tf = [Counter(d) for d in token_lists]
        df = Counter()
        for d in token_lists:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query_tokens, i):
        total = 0.0
        length = len(self.docs[i])
        for t in query_tokens:
            if t not in self.tf[i]:
                continue
            f = self.tf[i][t]
            denom = f + self.k1 * (1 - self.b + self.b * length / self.avg_len)
            total += self.idf[t] * f * (self.k1 + 1) / denom
        return total


class Retriever:
    def __init__(self):
        self.chunks = load_policy_chunks() + load_product_chunks()
        self.token_lists = [tokenize(c["index_text"]) for c in self.chunks]
        self.bm25 = BM25(self.token_lists)
        self.vocab = set(t for tl in self.token_lists for t in tl)

    def unknown_terms(self, query):
        """Customer words that appear nowhere in our policies/products and have no synonym that does."""
        out = []
        for t in dict.fromkeys(tokenize(query)):
            if t in self.vocab or any(s in self.vocab for s in SYNONYMS.get(t, [])):
                continue
            if t.isdigit():
                continue
            out.append(t)
        return out

    def search(self, query, k=3):
        """Return the top k results as dicts with chunk, score and coverage."""
        q = list(dict.fromkeys(tokenize(query)))
        if not q:
            return []
        expanded = list(dict.fromkeys(q + [s for t in q for s in SYNONYMS.get(t, [])]))
        results = []
        for i, chunk in enumerate(self.chunks):
            score = self.bm25.score(expanded, i)
            if score <= 0:
                continue
            chunk_tokens = set(self.token_lists[i])
            # coverage is measured on the CUSTOMER'S words: a word counts as covered
            # if it, or one of its synonyms, appears in the chunk
            covered = sum(1 for t in q if t in chunk_tokens or any(s in chunk_tokens for s in SYNONYMS.get(t, [])))
            results.append({"chunk": chunk, "score": score, "coverage": covered / len(q)})
        # rank by score x coverage, so a short chunk that misses one of the customer's words
        # cannot beat a chunk that covers all of them
        results.sort(key=lambda r: r["score"] * r["coverage"], reverse=True)
        return results[:k]


if __name__ == "__main__":
    import sys
    r = Retriever()
    print(f"{len(r.chunks)} chunks loaded")
    for q in sys.argv[1:]:
        print(f"\nQ: {q}")
        for hit in r.search(q, k=2):
            print(f"  score={hit['score']:.2f} cov={hit['coverage']:.2f} [{hit['chunk']['source']}] {hit['chunk']['text'][:90]}")