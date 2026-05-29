from urllib.parse import quote


def encode_storage_path(storage_path: str) -> str:
    """URL-encode each segment of a storage object key for Supabase REST paths."""
    return "/".join(quote(part, safe="") for part in storage_path.split("/"))
