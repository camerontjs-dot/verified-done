from dataclasses import dataclass


@dataclass
class Price:
    amount: float
    currency: str = "USD"

    def to_dict(self):
        return {"amount": self.amount, "currency": self.currency}
