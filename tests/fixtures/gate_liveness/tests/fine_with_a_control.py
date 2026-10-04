"""Fixture: a module that has a control beside its assertion. Expected LIVE."""


def test_something_true_about_the_fixture():
    assert sum([1, 2, 3]) == 6


def test_the_control_which_can_fail():
    """Named as a control, so D3 sees the module as falsifiable."""
    assert sum([1, 2, 3]) == 7  # the input that makes the one above fail
