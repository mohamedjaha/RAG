"""Port of the notebook's three evaluation suites (docs/notebook.ipynb cells 20-22) to the REST API.

The helpers (norm, IDK), the status logic (PASS / MISS (idk) / WRONG / HALLUCINATED /
EMPTY) and EVERY question and expected keyword in the three suites below are copied
VERBATIM from docs/notebook.ipynb cells 20, 21 and 22. They MUST NOT be edited,
reworded, added to or dropped - not even to make tests pass (AGENTS.md section 8;
milestones.md M5). The only change is transport: instead of calling rag.response(q)
in-process, each suite's PDF is indexed through POST /upload and every question is
sent through POST /ask.

Usage (with the API running, e.g. `uvicorn app:app --reload`):
    python tests/test_notebook_suites.py

Environment:
    API_BASE_URL   base URL of the API (default: http://127.0.0.1:8000)
    SLEEP_SECONDS  seconds to sleep before each question (default: 15, Groq rate limits)
"""

import os
import re
import sys
import time
import unicodedata

import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
DELAY = float(os.environ.get("SLEEP_SECONDS", "15"))

# PDFs live in <repo>/PDF; paths anchored at the repo root so the script also
# works when launched from another directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_PDF = os.path.join(_REPO_ROOT, "PDF", "lekl101.pdf")
STOREDIQ_PDF = os.path.join(_REPO_ROOT, "PDF", "IBMSIQDeploymentConfigGuide76021.pdf")


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[\u2010-\u2015\-]", " ", s)   # dashes/hyphens -> space
    s = re.sub(r"[’‘`'*_]", "", s)             # apostrophes, markdown
    s = s.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


IDK = ["i dont know", "not in", "no information", "not mentioned", "cannot", "not provided"]


TESTS_1 = [
    ("At what time and where was the narrator when the wave hit?", ["nine", "9", "havana riviera"]),
    ("How many floors did the Havana Riviera Hotel have?", ["twenty", "20"]),
    ("Who was the woman found in the car in the wall?", ["housekeeper"]),
    ("What jewelry did she wear?", ["serpent", "snake", "emerald"]),
    ("How did Frau Frieda get her name?", ["students"]),
    ("What did she answer when asked how she came to be in Vienna?", ["sell my dreams"]),
    ("How did the first dream she interpreted end?", ["caramel", "choked"]),
    ("What did Frau Frieda tell the narrator the night she told him to leave Vienna?", ["five years"]),
   
]


TESTS_2 = [

    ("What was the name of Neruda's wife?", ["matilde"]),
    ("What did Neruda say about prophetic dreams?", ["poetry"]),
    ("On which finger was the snake ring in Barcelona?", ["index"]),
    ("Which writer did the narrator say Neruda's dream was like?", ["borges"]),
    ("What color ink did Neruda use?", ["green"]),
    ("What did the ambassador say Frau Frieda did?", ["dreamed", "nothing"]),
    ("What is the significance of the title 'I Sell My Dreams'?", ["sell my dreams", "dream"]),
    # Unanswerable
    ("What is Neruda's favorite color?", None),
    ("What was Frau Frieda's real name?", None),
    ("What year does the Havana disaster take place?", None),
    ("What was the title of the book Neruda bought at Porter?", None),
]


TESTS_3 = [
    ("What are the components of the IBM StoredIQ solution?", ["gateway", "data server"]),
    ("What does the gateway do?", ["between the data servers", "application stack"]),
    ("What database does a DataServer - Classic use to store its index?", ["postgres"]),
    ("Where does a DataServer - Distributed store its index?", ["elasticsearch"]),
    ("How many vCPUs does the application stack need?", ["4"]),
    ("What is the default data disk size on a DataServer - Classic?", ["2 tb"]),
    ("What are the general size limits for a classic data server?", ["150 million", "500"]),
    ("How much index storage does metadata need per TB of source data?", ["30 gb"]),
    ("What minimum IOPS gives acceptable data server performance?", ["650"]),
    ("How much memory does each Elasticsearch node need?", ["32"]),
    ("How many gateways are recommended per data servers?", ["50"]),
    ("Which port must be open from the data server to the gateway?", ["11103"]),
    ("Which ports must be open between the gateway and the application stack?", ["8765", "5432"]),
    ("What port does Elasticsearch use for REST requests?", ["9200"]),
    ("How is IBM StoredIQ licensed?", ["rvu", "resource value unit"]),
    ("Which FIPS level does IBM StoredIQ support?", ["level 1"]),
    ("Which disk encryption does Elasticsearch use?", ["luks"]),
    ("What are the default credentials for the superadmin account?", ["admin"]),
    ("In what order should components be configured?", ["elasticsearch", "gateway"]),
    ("Is Microsoft Hyper-V supported for the Elasticsearch appliance?", ["not supported", "no"]),
    ("How many nodes does the default Elasticsearch cluster have?", ["three", "3"]),
    ("Which property is mandatory in cluster-setup.properties?", ["es_hosts"]),
    ("Which option is added to the setup command for a single node?", ["single-node", "single node"]),
    ("What is the minimum cluster size from which you can remove a node?", ["four", "4"]),
    ("Which command restarts services on data servers after changing the Elasticsearch node list?", ["deepfiler"]),
    # Unanswerable
    ("What is the price of an IBM StoredIQ license per RVU?", None),
    ("What is the release date of version 7.6.0.22?", None),
    ("How many concurrent users can the application stack support?", None),
]


def _detail(resp):
    """Best-effort 'detail' string from an error response body."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return resp.text


def upload(file_path):
    """POST /upload - multipart with field 'file'. Returns the JSON response or None."""
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/upload",
                files={"file": (os.path.basename(file_path), f, "application/pdf")},
                timeout=900,
            )
    except requests.RequestException as exc:
        print(f"Request error: {exc}")
        return None
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {_detail(resp)}")
        return None
    return resp.json()


def ask(question, files=None, k=None):
    """POST /ask with {"question": ..., "files": ..., "k": ...}; returns the "answer" string.

    files and k are omitted from the body when None. On any error the answer is ""
    so the question scores as EMPTY instead of crashing the whole run.
    """
    payload = {"question": question}
    if files is not None:
        payload["files"] = files
    if k is not None:
        payload["k"] = k
    try:
        resp = requests.post(f"{BASE_URL}/ask", json=payload, timeout=900)
    except requests.RequestException as exc:
        print(f"Request error: {exc}")
        return ""
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {_detail(resp)}")
        return ""
    try:
        body = resp.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        return str(body.get("answer", ""))
    return ""


def run_suite(title, pdf_path, tests):
    """Upload the suite's PDF once, run every question, print statuses and the score."""
    print(f"===== {title} =====")
    upload(pdf_path)
    passed = 0
    for q, kw in tests:
        time.sleep(DELAY)
        a = norm(str(ask(q)))
        idk = any(p in a for p in IDK)
        if not a:
            status = "EMPTY"
        elif kw:
            status = "PASS" if any(k in a for k in kw) else ("MISS (idk)" if idk else "WRONG")
        else:
            status = "PASS" if idk else "HALLUCINATED"
        passed += status == "PASS"
        print(f"{status:12} | {q}\n             -> {a[:120]}\n")
    print(f"Score: {passed}/{len(tests)}")
    return passed


def main():
    print(f"API: {BASE_URL} | delay before each question: {DELAY:g}s")
    s1 = run_suite("Suite 1 - 'I Sell My Dreams' (answerable)", STORY_PDF, TESTS_1)
    s2 = run_suite(
        "Suite 2 - 'I Sell My Dreams' (answerable + unanswerable)", STORY_PDF, TESTS_2
    )
    s3 = run_suite(
        "Suite 3 - IBM StoredIQ deployment guide (answerable + unanswerable)",
        STOREDIQ_PDF,
        TESTS_3,
    )
    print("===== Final summary =====")
    print(f"Suite 1: {s1}/{len(TESTS_1)}")
    print(f"Suite 2: {s2}/{len(TESTS_2)}")
    print(f"Suite 3: {s3}/{len(TESTS_3)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
