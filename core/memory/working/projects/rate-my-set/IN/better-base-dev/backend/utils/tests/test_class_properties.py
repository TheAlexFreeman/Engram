from __future__ import annotations

import gc
from typing import ClassVar

import pytest

from backend.utils.class_properties import cached_classproperty


class TestCachedClassproperty:
    @pytest.mark.parametrize(
        "initial_access_order",
        ["class_first", "instance_first", "instance_first_backwards", "mixture"],
    )
    def test_caching_mechanisms(self, initial_access_order):
        class A:
            x = 10

            @cached_classproperty
            def v(cls):
                return 1 + cls.x

        class B(A):
            x = 20
            y = 10

            @cached_classproperty
            def v(cls):
                return 2 + cls.y + super().v

        class C(B):
            y = 15

        class D:
            @cached_classproperty
            def v(cls):
                return 5 + A.v

        class E(D, C):
            @cached_classproperty
            def w(cls):
                return cls.v + 100 + cls.y

        class F(E):
            x = 50
            y = 30

        class G(F):
            @cached_classproperty
            def v(cls):
                return cls.w + 100

            @cached_classproperty
            def w(cls):
                return 200 + cls.x

        if initial_access_order == "class_first":
            assert A.v == 11
            A.x = 10
            assert A.v == 11
            B.y = 12
            assert B.v == 35
            B.y = 10
            assert B.v == 35
            assert C.v == 38
            assert B.v == 35
            assert A.v == 11
            assert B.v == 35
            assert C.v == 38
            assert A.v == 11
        elif initial_access_order in ("instance_first", "instance_first_backwards"):
            a = A()
            a.x = 100
            b = B()
            b.y = 200
            c = C()
            c.y = 300
            if initial_access_order == "instance_first":
                assert a.v == 11
                assert b.v == 33
                assert c.v == 38
                assert c.v == 38
                assert b.v == 33
                assert a.v == 11
            else:
                assert c.v == 38
                assert b.v == 33
                assert a.v == 11
                assert a.v == 11
                assert b.v == 33
                assert c.v == 38
        else:
            c = C()

            assert c.v == 38
            assert A.v == 11
            assert B.v == 33
            assert A.v == 11
            assert B.v == 33
            assert C.v == 38
            assert D.v == 16
            assert E.v == 16
            assert E.w == 131
            assert F.v == 16
            assert F.w == 146
            assert G.v == 350
            assert G.w == 250

            A.x = 0
            F.x = 60
            F.y = 55
            G.x = 100
            G.y = 900

            assert c.v == 38
            assert A.v == 11
            assert B.v == 33
            assert A.v == 11
            assert B.v == 33
            assert C.v == 38
            assert D.v == 16
            assert E.v == 16
            assert E.w == 131
            assert F.v == 16
            assert F.w == 146
            assert G.v == 350
            assert G.w == 250

    def test_garbage_collection(self):
        x = 5

        class A:
            y = 10

            @cached_classproperty
            def v(cls):
                return x + cls.y

        class B(A):
            y = 15

            @cached_classproperty
            def w(cls):
                return cls.v + cls.y

        v = A.__dict__["v"]
        w = B.__dict__["w"]
        assert isinstance(v, cached_classproperty), "Pre-condition"
        assert isinstance(w, cached_classproperty), "Pre-condition"
        v_cache = v._cache
        w_cache = w._cache

        assert len(v_cache) == 0
        assert len(w_cache) == 0

        assert A.v == 15
        assert len(v_cache) == 1
        assert [*v_cache][0] is A
        assert len(w_cache) == 0

        assert B.v == 20
        assert len(v_cache) == 2
        v_cache_tuple = tuple(v_cache)
        if v_cache_tuple[0] is A:
            assert v_cache_tuple == (A, B)
        else:
            assert v_cache_tuple == (B, A)
        assert len(w_cache) == 0

        B.y = 25
        b1 = B()
        b2 = B()

        assert b1.v == 20
        assert b2.v == 20
        assert B.v == 20
        assert b2.v == 20
        assert b1.v == 20
        assert len(v_cache) == 2
        v_cache_tuple = tuple(v_cache)
        if v_cache_tuple[0] is A:
            assert v_cache_tuple == (A, B)
        else:
            assert v_cache_tuple == (B, A)
        assert len(w_cache) == 0

        def construct_and_check_class(assert_w, assert_x):
            original_v_len = len(v_cache)

            class C(B):
                y = 30

                @cached_classproperty
                def w(cls):
                    nonlocal x

                    return_value = cls.v + x

                    x = x + 1

                    return return_value

            assert C not in v_cache
            assert len(v_cache) == original_v_len

            assert C.w == assert_w
            assert x == assert_x
            assert x == assert_x
            assert C.w == assert_w
            assert C.w == assert_w
            assert x == assert_x

            assert len(v_cache) == original_v_len + 1
            assert C in v_cache

        v_cache_len = len(v_cache)
        v_cache_keys = set(v_cache.keys())
        construct_and_check_class(40, 6)
        assert x == 6
        gc.collect()
        assert len(v_cache) == v_cache_len
        assert set(v_cache.keys()) == v_cache_keys

        v_cache_len = len(v_cache)
        v_cache_keys = set(v_cache.keys())
        construct_and_check_class(42, 7)
        assert x == 7
        gc.collect()
        assert len(v_cache) == v_cache_len
        assert set(v_cache.keys()) == v_cache_keys

    def test_garbage_collection_deeper_nesting_and_cyclic_refs(self):
        x = 5

        class A:
            y = 10

            @cached_classproperty
            def v(cls):
                return x + cls.y

        class B(A):
            y = 15

            @cached_classproperty
            def w(cls):
                return cls.v + cls.y

        v = A.__dict__["v"]
        w = B.__dict__["w"]
        assert isinstance(v, cached_classproperty), "Pre-condition"
        assert isinstance(w, cached_classproperty), "Pre-condition"
        v_cache = v._cache
        w_cache = w._cache

        def make_nested_case_level_one():
            class C(B):
                y = 30

                @cached_classproperty
                def w(cls):
                    nonlocal x

                    x = x + 1

                    return super().w + cls.v

                @cached_classproperty
                def w2(cls):
                    return cls.w

            class D(C):
                @cached_classproperty
                def w(cls):
                    nonlocal x

                    x = x + 5

                    return super().w + cls.v

                @cached_classproperty
                def w3(cls):
                    return cls.w

            def make_nested_case_level_two():
                class E1(C):
                    y = 100

                    @cached_classproperty
                    def z(cls):
                        return cls.w

                class E2(D):
                    y = 200

                    @cached_classproperty
                    def z(cls):
                        return cls.w

                assert E1.w2
                assert E1.w
                assert E1.v
                assert E2.v
                assert E2.w
                assert E2.w3
                assert E1.v
                assert E1.w
                assert E1.w2
                assert E2.v
                assert E2.w
                assert E2.w3

                assert x == 12
                assert len(v_cache) == 2
                assert len(w_cache) == 2

                c = {1: E1, 2: E2}

                return c

            c = make_nested_case_level_two()

            assert D.w3
            assert D.w
            assert D.v
            assert C.v
            assert C.w
            assert C.w2
            assert D.v
            assert D.w
            assert D.w3
            assert C.v
            assert C.w
            assert C.w2

            assert c[1]
            assert c[2]

            assert x == 19
            assert len(v_cache) == 4
            assert len(w_cache) == 4

            c[1].__dict__["z"].__get__(None, B)
            c[1].__dict__["z"].__get__(None, C)
            c[1].__dict__["z"].__get__(None, D)
            c[2].__dict__["z"].__get__(None, D)
            c[2].__dict__["z"].__get__(None, C)
            c[2].__dict__["z"].__get__(None, B)
            c[1].__dict__["z"].__get__(None, B)
            c[1].__dict__["z"].__get__(None, C)
            c[1].__dict__["z"].__get__(None, D)
            c[2].__dict__["z"].__get__(None, D)
            c[2].__dict__["z"].__get__(None, C)
            c[2].__dict__["z"].__get__(None, B)

            del c[1]

        make_nested_case_level_one()

        gc.collect()

        assert len(v_cache) == 1
        assert len(w_cache) == 1
        assert [*v_cache][0] is B
        assert [*w_cache][0] is B


class CheckTypeHandling:
    x: ClassVar[int] = 10

    y: int = 20

    def __init__(self, y, z):
        self.y = y
        self.z = z

    @cached_classproperty
    def a_property_name(cls) -> int:
        return cls.x + cls.y + 5

    @classmethod
    def cls_get_total(cls):
        return cls.a_property_name

    def get_total(self):
        return self.a_property_name


# --- Reveal types (If wanting to check can uncomment) ---
# from typing import reveal_type
# _check_type_handling = CheckTypeHandling(30, 50)
# reveal_type(CheckTypeHandling.a_property_name)
# reveal_type(CheckTypeHandling.cls_get_total)
# reveal_type(CheckTypeHandling.get_total)
# reveal_type(_check_type_handling.a_property_name)
# reveal_type(_check_type_handling.cls_get_total)
# reveal_type(_check_type_handling.get_total)
# ---                                                  ---
