"""Fetch a bounded official MPU-rPPG public sample into ignored local cache."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = (ROOT / "docs/ReferenceDataset/external_cache/mpu_public_sample").resolve()
API = "https://api.figshare.com/v2/articles/29377835"
IDS = [55553414, 55553420, 55553426, 55553435, 55553429]


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AIVitals-research-QC"}), timeout=45)


def main():
    if not CACHE.is_relative_to((ROOT / "docs/ReferenceDataset/external_cache").resolve()):
        raise ValueError("Cache path escapes allowed directory")
    with request(API) as response:
        article = json.load(response)
    if article.get("license", {}).get("name") != "CC BY 4.0":
        raise ValueError("Recheck public sample license before download")
    files = {item["id"]: item for item in article["files"]}
    selected = [files[file_id] for file_id in IDS]
    if sum(item["size"] for item in selected) > 150_000_000:
        raise ValueError("Selected download exceeds bounded 150 MB scope")
    CACHE.mkdir(parents=True, exist_ok=True)
    records = []
    for item in selected:
        if Path(item["name"]).name != item["name"] or Path(item["name"]).suffix not in {".csv", ".mp4"}:
            raise ValueError("Unexpected file name/type in source metadata")
        target = CACHE / f"{item['id']}_{item['name']}"
        if target.exists():
            raise FileExistsError(f"Existing cache: {target}; verify instead of overwrite")
        temporary = target.with_suffix(target.suffix + ".part")
        print(f"Downloading file {item['id']} ({item['size']} bytes)", flush=True)
        with request(item["download_url"]) as response, temporary.open("xb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if temporary.stat().st_size != item["size"]:
            raise ValueError(f"Incomplete download retained at {temporary}")
        with temporary.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "md5").hexdigest()
        if item.get("computed_md5") and checksum != item["computed_md5"]:
            raise ValueError(f"Checksum mismatch retained at {temporary}")
        temporary.rename(target)
        records.append({"file_id": item["id"], "original_name": item["name"], "local_name": target.name,
                        "size": item["size"], "md5": checksum, "download_url": item["download_url"]})
    (CACHE / "provenance.json").write_text(json.dumps({"source": API, "article_title": article["title"],
        "license": article["license"], "files": records,
        "pairing_verified": False, "notes": "Public sample only. File-ID adjacency is not proof of pairing. No request or signature sent for full data."}, indent=2) + "\n", encoding="utf-8")
    print("Download complete; pairing/timing must be validated separately.", flush=True)


if __name__ == "__main__":
    main()
