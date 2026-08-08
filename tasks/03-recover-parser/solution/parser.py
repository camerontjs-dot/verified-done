def parse_ints(s):
    if not s:
        return []
    return [int(x) for x in s.split(",")]
