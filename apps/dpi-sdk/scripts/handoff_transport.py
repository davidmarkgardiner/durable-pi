"""Local hub or authenticated local backend connection settings."""
from pathlib import Path
import urllib.parse


def connection(url, device, backend_env=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password:
        raise ValueError("Coordinator requires a loopback HTTP endpoint")
    headers = {"Content-Type": "application/json"}
    if backend_env:
        tokens = [line.partition("=")[2].strip() for line in Path(backend_env).read_text().splitlines() if line.startswith("DPI_TOKEN=")]
        if len(tokens) != 1 or len(tokens[0]) < 32:
            raise ValueError("Backend environment must contain one valid DPI_TOKEN")
        headers["Authorization"] = "Bearer " + tokens[0]
        return url.rstrip("/") + "/v1", headers
    return url.rstrip("/") + "/api/devices/" + urllib.parse.quote(device, safe="") + "/v1", headers
