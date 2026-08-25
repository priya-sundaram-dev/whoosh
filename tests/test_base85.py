"""Tests for whoosh.support.base85.

The module exists to encode integers so that the encoded strings sort in the
same order as the integers -- that is the property whoosh2's sortable_*_to_text
depends on, and it is the thing a well-meaning refactor to base64.b85encode
would silently break. A roundtrip test alone would not catch that, so the
ordering and fixed-width invariants are asserted directly.
"""

import random

from whoosh.codec.whoosh2 import sortable_int_to_text, sortable_long_to_text
from whoosh.support import base85
from whoosh.support.base85 import b85chars, from_base85, to_base85

# One past the largest value each width can hold.
INT_LIMIT = 85**5
LONG_LIMIT = 85**10


def test_integer_roundtrip():
    for x in [0, 1, 84, 85, 86, 1000, 2**31, INT_LIMIT - 1]:
        assert from_base85(to_base85(x)) == x

    for x in [0, 1, 2**31, 2**48, INT_LIMIT, LONG_LIMIT - 1]:
        assert from_base85(to_base85(x, islong=True)) == x


def test_byte_codec_removed():
    # The Python-2-era byte codec could not run on Python 3 and was dead code;
    # make sure it is not reintroduced without a working implementation.
    assert not hasattr(base85, "b85encode")
    assert not hasattr(base85, "b85decode")


def test_alphabet_is_in_ascii_order():
    # The reason for the custom alphabet. base64.b85encode's alphabet is not
    # ordered, so it cannot be substituted here without breaking sort order.
    assert list(b85chars) == sorted(b85chars)
    assert len(b85chars) == 85
    assert len(set(b85chars)) == 85


def test_encoding_is_fixed_width():
    # The other half of sortability: a shorter string must never compare less
    # than a longer one just for being shorter.
    assert all(len(to_base85(x)) == 5 for x in (0, 1, 84, INT_LIMIT - 1))
    assert all(len(to_base85(x, islong=True)) == 10 for x in (0, 1, LONG_LIMIT - 1))


def test_encoding_preserves_order():
    numbers = sorted(random.sample(range(INT_LIMIT), 200))
    encoded = [to_base85(x) for x in numbers]
    assert encoded == sorted(encoded)


def test_encoding_preserves_order_long():
    # randrange rather than sample: range(85 ** 10) is too large for
    # random.sample to take a len() of.
    numbers = sorted(random.randrange(LONG_LIMIT) for _ in range(200))
    encoded = [to_base85(x, islong=True) for x in numbers]
    assert encoded == sorted(encoded)


def test_adjacent_values_stay_adjacent_in_order():
    # Catches an off-by-one in the carry that random sampling could miss.
    encoded = [to_base85(x) for x in range(84, 87)]
    assert encoded == sorted(encoded)


def test_sortable_int_to_text_preserves_order():
    # The invariant exercised through whoosh2's own API, which is what
    # actually depends on it.
    numbers = sorted(random.sample(range(INT_LIMIT), 100))
    assert [sortable_int_to_text(x) for x in numbers] == sorted(
        sortable_int_to_text(x) for x in numbers
    )


def test_sortable_long_to_text_preserves_order():
    numbers = sorted(random.randrange(LONG_LIMIT) for _ in range(100))
    assert [sortable_long_to_text(x) for x in numbers] == sorted(
        sortable_long_to_text(x) for x in numbers
    )
