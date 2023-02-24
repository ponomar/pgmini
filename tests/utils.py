def compact(sql: str) -> str:
    lines = [i.strip() for i in sql.split('\n') if i.strip()]
    res = []
    for curr, nxt in zip(lines, lines[1:] + [''], strict=True):
        res.append(curr)
        if not (curr.endswith('(') or nxt.startswith(')')):
            # do not add space after opening bracket and before closing one
            res.append(' ')
    return ''.join(res).strip()
