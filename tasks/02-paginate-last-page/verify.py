from paginate import paginate

assert paginate(list(range(10)), 3) == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
assert paginate(list(range(6)), 3) == [[0, 1, 2], [3, 4, 5]]
assert paginate([], 3) == []
flat = [x for page in paginate(list(range(7)), 2) for x in page]
assert flat == list(range(7)), flat
print("ok")
