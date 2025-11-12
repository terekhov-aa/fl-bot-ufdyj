import re
from typing import Optional

EXTERNAL_ID_PATTERN = re.compile(r"/projects/(\d+)/")


def extract_external_id(url: str | None) -> Optional[int]:
    if not url:
        return None
    match = EXTERNAL_ID_PATTERN.search(url)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None
