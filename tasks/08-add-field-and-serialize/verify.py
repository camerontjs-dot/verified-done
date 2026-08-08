from model import User
from serialize import serialize_user

u = User("Ada", "ada@x.com")
assert serialize_user(u) == {"name": "Ada", "email": "ada@x.com"}, serialize_user(u)
print("ok")
