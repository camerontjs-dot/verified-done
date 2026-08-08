from dataclasses import dataclass


@dataclass
class Price:
    amount: float

    def to_dict(self):
        return {"amount": self.amount}
