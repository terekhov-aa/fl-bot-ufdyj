import json
import requests

BASE_URL = "http://localhost:3000"
TEST_URL = "https://docs.google.com/document/d/1IMeBO8N_GKkneI3RYh54MA7Eay-ZsQgd/edit?usp=sharing"


def main():
    payload = {"url": TEST_URL}
    resp = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=60)
    print("Status:", resp.status_code)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()
