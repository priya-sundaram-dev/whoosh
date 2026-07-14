"""Guards for PEP 561 typing support.

These tests ensure Whoosh advertises itself as a typed package (ships a
``py.typed`` marker) and that the type annotations on the most-used public
API entry points stay present and importable, so downstream users get
editor autocompletion and ``mypy``/``pyright`` checking out of the box.

See gh#3.
"""

import inspect
import os

import whoosh
from whoosh import fields, index


def test_py_typed_marker_ships_with_package():
    """A ``py.typed`` marker must sit next to the package's ``__init__``
    so PEP 561-compatible type checkers treat Whoosh as typed."""
    pkg_dir = os.path.dirname(whoosh.__file__)
    marker = os.path.join(pkg_dir, "py.typed")
    assert os.path.exists(marker), "py.typed marker is missing from the package"


def test_public_entry_points_are_annotated():
    """The convenience functions most users call first carry annotations."""
    for func in (index.create_in, index.open_dir, index.exists_in, index.exists):
        sig = inspect.signature(func)
        # Return annotation present...
        assert sig.return_annotation is not inspect.Signature.empty, (
            f"{func.__name__} is missing a return annotation"
        )
        # ...and every parameter annotated.
        for name, param in sig.parameters.items():
            assert param.annotation is not inspect.Parameter.empty, (
                f"{func.__name__}: parameter {name!r} is missing an annotation"
            )


def test_versionstring_is_annotated():
    sig = inspect.signature(whoosh.versionstring)
    assert sig.return_annotation is not inspect.Signature.empty


def test_schema_public_methods_are_annotated():
    """``Schema`` is the most-imported public class; its common methods
    carry annotations so downstream code type-checks (gh#3)."""
    for name in (
        "copy",
        "items",
        "names",
        "add",
        "remove",
        "stored_names",
        "scorable_names",
        "indexable_fields",
        "has_scorable_fields",
    ):
        func = getattr(fields.Schema, name)
        sig = inspect.signature(func)
        assert sig.return_annotation is not inspect.Signature.empty, (
            f"Schema.{name} is missing a return annotation"
        )
