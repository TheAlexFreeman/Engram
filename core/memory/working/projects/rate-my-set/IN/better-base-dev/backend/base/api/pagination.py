from __future__ import annotations

from rest_framework.pagination import PageNumberPagination as DRFPageNumberPagination
from rest_framework.response import Response


class DefaultPageNumberPagination(DRFPageNumberPagination):
    page_query_param = "page_number"
    page_size_query_param = "page_size"
    page_size = 25
    max_page_size = 200

    def get_paginated_response(self, data):
        assert self.page is not None, "Pre-condition"

        page_number = self.page.number
        last_page_number = self.page.paginator.num_pages
        page_size = self.page.paginator.per_page
        has_previous = self.page.has_previous()
        has_next = self.page.has_next()
        nearby_page_numbers = self.page.paginator.get_elided_page_range(page_number)
        total_num_records = self.page.paginator.count

        return Response(
            {
                "pagination": {
                    "page_number": page_number,
                    "last_page_number": last_page_number,
                    "page_size": page_size,
                    "has_previous": has_previous,
                    "has_next": has_next,
                    "nearby_page_numbers": nearby_page_numbers,
                    "total_num_records": total_num_records,
                },
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "pagination": {
                    "type": "object",
                    "required": [
                        "page_number",
                        "last_page_number",
                        "page_size",
                        "has_previous",
                        "has_next",
                        "nearby_page_numbers",
                    ],
                    "properties": {
                        "page_number": {"type": "integer"},
                        "last_page_number": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "has_previous": {"type": "boolean"},
                        "has_next": {"type": "boolean"},
                        "nearby_page_numbers": {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "string", "enum": ["...", "…"]},
                                ]
                            },
                        },
                    },
                },
                "results": schema,
            },
        }
