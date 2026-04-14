from __future__ import annotations

import json
from functools import singledispatch
from typing import Any

from django.http import HttpResponse
from pyquery import PyQuery as pq


@singledispatch
def extract_initial_data(from_: Any) -> dict[str, Any]:
    assert isinstance(from_, str), "Current pre-condition"

    d = pq(from_)
    script = d("script#initial_server_data_provided_for_web")
    json_text = script.text()

    d = json.loads(json_text)
    assert d and isinstance(d, dict), "Current post-condition"

    return d


@extract_initial_data.register
def _(from_: HttpResponse) -> dict[str, Any]:
    return extract_initial_data(from_.content.decode("utf-8"))
