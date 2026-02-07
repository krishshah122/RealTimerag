import faiss
import json
import os

DATA_DIR = "data"
INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
DOC_PATH = os.path.join(DATA_DIR, "docs.json")
VERSION_PATH = os.path.join(DATA_DIR, "version.txt")


def current_version():
    """
    Returns current data version.
    Creates version.txt if missing.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(VERSION_PATH):
        with open(VERSION_PATH, "w") as f:
            f.write("0")
        return 0

    with open(VERSION_PATH) as f:
        return int(f.read().strip())


def bump_version():
    v = current_version() + 1
    with open(VERSION_PATH, "w") as f:
        f.write(str(v))
    return v


def save(index, docs):
    os.makedirs(DATA_DIR, exist_ok=True)

    faiss.write_index(index, INDEX_PATH)

    with open(DOC_PATH, "w") as f:
        json.dump(docs, f)

    bump_version()   # 🔥 important


def load():
    if not os.path.exists(INDEX_PATH) or not os.path.exists(DOC_PATH):
        return None, None

    index = faiss.read_index(INDEX_PATH)

    with open(DOC_PATH) as f:
        docs = json.load(f)

    return index, docs
