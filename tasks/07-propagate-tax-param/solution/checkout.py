from cart import total


def checkout(items, tax_rate=0.0):
    return total(items, tax_rate=tax_rate)
