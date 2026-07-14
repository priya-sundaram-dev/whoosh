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


def test_field_type_constructors_are_annotated():
    """The field-type constructors users write in every ``Schema`` (TEXT,
    ID, KEYWORD, NUMERIC, DATETIME, BOOLEAN, STORED, IDLIST, COLUMN) carry
    parameter and return annotations, so editors autocomplete their kwargs
    and type checkers verify field definitions (gh#3)."""
    for name in (
        "TEXT",
        "ID",
        "IDLIST",
        "KEYWORD",
        "NUMERIC",
        "DATETIME",
        "BOOLEAN",
        "STORED",
        "COLUMN",
    ):
        cls = getattr(fields, name)
        sig = inspect.signature(cls.__init__)
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty, (
                f"{name}.__init__: parameter {pname!r} is missing an annotation"
            )


def test_qparser_entry_points_are_annotated():
    """QueryParser and the premade parser factories carry type hints so
    editors and type checkers can assist when building queries (gh#3)."""
    from whoosh.qparser import default as qpdefault

    # QueryParser core methods.
    for name in ("__init__", "parse", "parse_", "process", "tag"):
        method = getattr(qpdefault.QueryParser, name)
        sig = inspect.signature(method)
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty, (
                f"QueryParser.{name}: parameter {pname!r} is missing an annotation"
            )

    # Premade parser factory functions.
    for name in ("MultifieldParser", "SimpleParser", "DisMaxParser"):
        func = getattr(qpdefault, name)
        sig = inspect.signature(func)
        assert sig.return_annotation is not inspect.Signature.empty, (
            f"{name}: missing a return annotation"
        )


def test_searching_layer_entry_points_are_annotated():
    """The searching layer's public API (Searcher, Results, Hit, ResultsPage)
    carries type hints so editors and type checkers can assist when running
    queries and reading results (gh#3)."""
    from whoosh import searching

    # Searcher public query methods.
    for name in ("__init__", "search", "search_page", "search_with_collector"):
        method = getattr(searching.Searcher, name)
        sig = inspect.signature(method)
        for pname, param in sig.parameters.items():
            if pname in ("self", "kwargs"):
                continue
            assert param.annotation is not inspect.Parameter.empty, (
                f"Searcher.{name}: parameter {pname!r} is missing an annotation"
            )

    # Result container constructors.
    for cls in (searching.Results, searching.Hit, searching.ResultsPage):
        sig = inspect.signature(cls.__init__)
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty, (
                f"{cls.__name__}.__init__: parameter {pname!r} missing annotation"
            )
