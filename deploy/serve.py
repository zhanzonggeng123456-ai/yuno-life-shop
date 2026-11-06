"""Start the single-worker API on an explicitly mounted persistent volume."""
import os
import tempfile
from pathlib import Path


def configure_storage():
    root = Path(os.environ.get("YUNO_DATA_DIR", "/data")).resolve()
    if os.environ.get("YUNO_REQUIRE_PERSISTENT_VOLUME", "1") != "0":
        if not root.is_mount():
            raise RuntimeError("YUNO requires a persistent volume mounted at YUNO_DATA_DIR")
    root.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, fallback in (("YUNO_DB_PATH", root / "db" / "yuno.db"),
                          ("YUNO_UPLOAD_DIR", root / "uploads")):
        path = Path(os.environ.get(key, str(fallback))).resolve()
        if not path.is_relative_to(root) or path == root:
            raise RuntimeError(f"{key} must be inside YUNO_DATA_DIR")
        paths[key] = path
    paths["YUNO_DB_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["YUNO_UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    # Fail before accepting traffic if the mounted storage isn't writable.
    for directory in (paths["YUNO_DB_PATH"].parent, paths["YUNO_UPLOAD_DIR"]):
        with tempfile.TemporaryFile(dir=directory) as probe:
            probe.write(b"yuno-storage-check")
            probe.flush()
            os.fsync(probe.fileno())
    os.environ.update({key: str(path) for key, path in paths.items()})
    return root


def main():
    configure_storage()
    port = int(os.environ.get("PORT", os.environ.get("YUNO_PORT", "8000")))
    if not 1 <= port <= 65535:
        raise RuntimeError("Invalid listening port")
    import uvicorn
    # No wildcard trust of arbitrary forwarded IP headers. A hosting provider's
    # trusted proxy addresses can be configured explicitly once verified.
    uvicorn.run("deploy.gateway:app", host="0.0.0.0", port=port, workers=1,
                proxy_headers=True,
                forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"))


if __name__ == "__main__":
    main()
