import json

import requests

BASE_URL = "http://localhost:3000"
TEST_URL = "https://docs.google.com/document/d/1IMeBO8N_GKkneI3RYh54MA7Eay-ZsQgd/edit?usp=sharing"


def main() -> None:
    response = requests.post(f"{BASE_URL}/analyze", json={"url": TEST_URL}, timeout=30)
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to decode response: {exc}")
        print(response.text)


if __name__ == "__main__":
    main()
