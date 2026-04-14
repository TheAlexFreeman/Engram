from __future__ import annotations

from copy import copy, deepcopy
from typing import Any

import pytest

from backend.utils.dictionaries import (
    DeepKeyValueTransformFuncReturnType,
    json_like_dict_deep_key_value_transform,
)


class TestJsonLikeDictDeepKeyValueTransform:
    def test_simple_starting_dict(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
            "d": "some value",
            "e": ("more", "values"),
            "f": "",
            "g": "",
            "h": "over here",
        }

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k == "a":
                return None
            if k == "b":
                return (k, 5)
            if k == "c":
                return (k, v)
            if k == "d":
                return ("new_d", "new some value")
            if k == "f":
                return []
            if k == "h":
                return [("h1", 1), ("h2", 2)]
            return None

        json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert d == {
            "a": 1,
            "b": 5,
            "c": [1, 2, 3, 4],
            "new_d": "new some value",
            "e": ("more", "values"),
            "g": "",
            "h1": 1,
            "h2": 2,
        }

    def test_simple_starting_list(self):
        counter = 0

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            nonlocal counter

            if t[0] == "a":
                counter += 1
                return (t[0], f"{t[1]}{counter - 1}")

            return None

        d = [1, 2, {"a": "b", "c": "d"}, [1, 2, {"a": "b", "c": "d"}]]

        json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert d == [1, 2, {"a": "b0", "c": "d"}, [1, 2, {"a": "b1", "c": "d"}]]

    def test_replacing_same_key_with_different_value(self):
        d = {"a": 1, "b": 2}

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k in ("a", "b"):
                return (k, v * 2)
            return None

        json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert d == {"a": 2, "b": 4}

    def test_replacing_same_key_with_same_value(self):
        o1 = object()
        d = {"a": 1, "b": [2, 4], "c": o1}
        initial_b = d["b"]
        initial_d = copy(d)

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            return t

        json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert d == {"a": 1, "b": [2, 4], "c": o1}
        assert d == initial_d
        assert d["b"] is initial_b

    def test_replacing_same_key_with_multiple_key_value_pairs(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
            "d": 18,
            "e": 24,
            "f": 30,
            "g": 36,
            "h": 42,
        }

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k == "a":
                return [("a", 3), ("a1", 4), ("a", 5)]
            if k == "b":
                return [("b", 6), ("b1", 8), ("b2", 10)]
            if k == "c":
                return [("c", "c1")]
            if k == "d":
                return []
            if k == "f":
                return [("f1", "f11"), ("f2", "f22")]
            if k == "g":
                return [(k, v)]
            if k == "h":
                return [(k, v), (k, v)]
            return None

        json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert d == {
            "a": 5,
            "a1": 4,
            "b": 6,
            "b1": 8,
            "b2": 10,
            "c": "c1",
            "e": 24,
            "f1": "f11",
            "f2": "f22",
            "g": 36,
            "h": 42,
        }

    def test_deep_more_complex(self):
        d = {
            "a": 5,
            "access_token": "duck",
            "b": 6,
            "c": {
                "list": [
                    {"access_id_token": "squirrel", "18": 5},
                    {"secret_token": 18},
                    {},
                    [{}, {}, []],
                    {"id": 7, "over": "the top", "some_token": 15},
                ]
            },
            "d": [{"access_token": 15}],
        }

        def f(t: tuple[Any, Any]):
            if "token" in t[0]:
                return (t[0], "***redacted***")
            return None

        json_like_dict_deep_key_value_transform(d, f, mutate_in_place=True)

        assert d == {
            "a": 5,
            "access_token": "***redacted***",
            "b": 6,
            "c": {
                "list": [
                    {"access_id_token": "***redacted***", "18": 5},
                    {"secret_token": "***redacted***"},
                    {},
                    [{}, {}, []],
                    {"id": 7, "over": "the top", "some_token": "***redacted***"},
                ]
            },
            "d": [{"access_token": "***redacted***"}],
        }

    def test_mutate_in_place(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
        }

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k == "b":
                return []
            if k == "c":
                v.append(5)
                return t
            return (k, v)

        r = json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        assert r == {"a": 1, "c": [1, 2, 3, 4, 5]}
        assert d == r
        assert d is r

    def test_copy_default_copier(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
        }
        initial_d = deepcopy(d)

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k == "b":
                return []
            if k == "c":
                v.append(5)
                return t
            return (k, v)

        r = json_like_dict_deep_key_value_transform(d, func, mutate_in_place=False)

        assert r == {"a": 1, "c": [1, 2, 3, 4, 5]}
        assert d != r
        assert d is not r
        assert d == initial_d

    def test_copy_custom_copier(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
        }
        initial_d = deepcopy(d)

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            k, v = t
            if k == "b":
                return []
            if k == "c":
                v.append(5)
                return t
            return (k, v)

        r = json_like_dict_deep_key_value_transform(
            d, func, mutate_in_place=False, copier=copy
        )

        assert r == {"a": 1, "c": [1, 2, 3, 4, 5]}
        assert d["c"] == [1, 2, 3, 4, 5]
        assert d != r
        assert d is not r
        assert d == {"a": 1, "b": 2, "c": [1, 2, 3, 4, 5]}
        assert d != initial_d

    def test_incorrect_return_type(self):
        d = {
            "a": 1,
            "b": 2,
            "c": [1, 2, 3, 4],
        }

        def func(t: tuple[Any, Any]) -> DeepKeyValueTransformFuncReturnType:
            return "duck"  # type: ignore[return-value]

        with pytest.raises(TypeError) as exc_info:
            json_like_dict_deep_key_value_transform(d, func, mutate_in_place=True)

        e = exc_info.value
        assert (
            e.args[0]
            == "Unexpected return value type from `func(('a', 1))`: `<class 'str'>`"
        )
