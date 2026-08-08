from money import Price

p = Price(amount=5.0)
assert p.currency == "USD", "default currency should be USD"
assert p.to_dict() == {"amount": 5.0, "currency": "USD"}, p.to_dict()
q = Price(amount=1.0, currency="EUR")
assert q.to_dict() == {"amount": 1.0, "currency": "EUR"}, q.to_dict()
print("ok")
