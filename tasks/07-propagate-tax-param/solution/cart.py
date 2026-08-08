def total(items, tax_rate=0.0):
    subtotal = sum(item["price"] * item["qty"] for item in items)
    return subtotal * (1 + tax_rate)
