from rounding import round_half_up

# existing behaviour that must be preserved
assert round_half_up(2.4) == 2
assert round_half_up(2.6) == 3
# regression cases that currently fail under banker's rounding
assert round_half_up(0.5) == 1
assert round_half_up(2.5) == 3
assert round_half_up(3.5) == 4
print("ok")
