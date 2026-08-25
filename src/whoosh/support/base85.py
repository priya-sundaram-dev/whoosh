"""
This module contains base85 encoding and decoding functions for integers.
The whoosh.util.numeric module contains faster variants.

Unlike the standard ascii85/base85 alphabets, the character set here is in
ASCII order, so encoded strings sort in the same order as the integers they
encode. whoosh.codec.whoosh2's sortable_int_to_text/sortable_long_to_text
rely on that property, so the alphabet must not be swapped for the one in
the stdlib base64 module -- base64.b85encode's alphabet is not ordered, and
substituting it would silently break sorted-order lookups on existing
indexes.

Encoded values are also fixed width (5 characters, or 10 with islong=True),
which is the other half of what makes them sortable: a shorter string must
never compare less than a longer one just for being shorter.

Modified from:
http://paste.lisp.org/display/72815
"""

# Instead of using the character set from the ascii85 algorithm, I put the
# characters in order so that the encoded text sorts properly (my life would be
# a lot easier if they had just done that from the start)
b85chars = (
    "!$%&*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "^_abcdefghijklmnopqrstuvwxyz{|}~"
)
b85dec = {}
for i in range(len(b85chars)):
    b85dec[b85chars[i]] = i


# Integer encoding and decoding functions


def to_base85(x, islong=False):
    "Encodes the given integer using base 85."

    size = 10 if islong else 5
    rems = ""
    for i in range(size):
        rems = b85chars[x % 85] + rems
        x //= 85
    return rems


def from_base85(text):
    "Decodes the given base 85 text into an integer."

    acc = 0
    for c in text:
        acc = acc * 85 + b85dec[c]
    return acc
