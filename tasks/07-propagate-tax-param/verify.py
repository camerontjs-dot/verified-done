from checkout import checkout
from cart import total

items = [{"price": 10.0, "qty": 2}]  # subtotal 20.0
assert checkout(items) == 20.0, checkout(items)
assert round(checkout(items, tax_rate=0.1), 2) == 22.0
assert round(total(items, tax_rate=0.25), 2) == 25.0
print("ok")
