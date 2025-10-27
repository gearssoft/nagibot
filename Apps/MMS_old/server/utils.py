
def deep_merge(a: dict, b: dict) -> dict:
    for key, value in b.items():
        if key in a and isinstance(a[key], dict) and isinstance(value, dict):
            deep_merge(a[key], value)
        else:
            a[key] = value
    return a


def _get_by_path(data: dict, path: str):
    """
    점 표기 경로 조회: "pos.x" -> data["pos"]["x"]
    존재하지 않으면 None 반환
    """
    cur = data
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur
