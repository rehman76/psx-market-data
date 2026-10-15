"""Conservative PSX closing-file date-template expansion.

Only an exact YYYY-MM-dd or YYYY-MM-DD token is supported. This only resolves
a path: it does NOT establish that the resulting endpoint exists or is licensed.
"""
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from scripts.freshness_core import expected_weekday

TOKENS = ("YYYY-MM-dd", "YYYY-MM-DD")

def resolve_download_url(template, now=None):
    if not isinstance(template, str) or not template.strip():
        raise ValueError("EMPTY_OFFICIAL_DOWNLOAD_URL")
    template = template.strip()
    parsed = urlsplit(template)
    if (parsed.scheme != 'https' or parsed.hostname != 'dps.psx.com.pk'
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("UNAUTHORIZED_OFFICIAL_DOWNLOAD_URL")
    # Date templating only applies to the path, not query credentials.
    path=parsed.path
    present=[token for token in TOKENS if token in path]
    if sum(path.count(token) for token in TOKENS)>1:
        raise ValueError("AMBIGUOUS_DATE_TEMPLATE")
    if present:
        session=expected_weekday(now).isoformat()
        path=path.replace(present[0],session)
    if "YYYY" in path or "yyyy" in path:
        raise ValueError("UNSUPPORTED_DATE_TEMPLATE")
    url=urlunsplit((parsed.scheme,parsed.netloc,path,parsed.query,''))
    return url, (expected_weekday(now).isoformat() if present else None)
