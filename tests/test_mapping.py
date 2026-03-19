
import pandas as pd
from addrmap.mapping import get_digits

def test_get_digits():
    assert get_digits("12A") == "12"
    assert get_digits("B34") == "34"
    assert get_digits("No number") == ""
