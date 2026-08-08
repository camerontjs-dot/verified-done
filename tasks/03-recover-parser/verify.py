from parser import parse_ints

assert parse_ints("1,2,3") == [1, 2, 3]
assert parse_ints("") == []
assert parse_ints("5") == [5]
print("ok")
