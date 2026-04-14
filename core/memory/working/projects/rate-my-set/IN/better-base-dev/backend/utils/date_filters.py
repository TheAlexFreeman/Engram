from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from datetime import timezone as python_timezone
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

import structlog
from django.utils import timezone
from rest_framework import serializers

logger = structlog.stdlib.get_logger()


class DateFilterOps:
    def __init__(self, *, set_now_to: datetime | Literal["default"] = "default"):
        if set_now_to == "default":
            self._now = None
        else:
            self._now = set_now_to

    def extract_structured_date_filtering_info(
        self,
        *,
        date_field_name: str,
        tz_raw: str,
        date_preset_raw: str,
        custom_date_start_raw: str | None,
        custom_date_end_raw: str | None,
    ) -> StructuredDateFilteringInfo:
        assert tz_raw and date_preset_raw, "Current pre-condition"

        zone_info: ZoneInfo | python_timezone = UTC
        try:
            zone_info = ZoneInfo(tz_raw)
        except Exception:
            logger.exception(
                "Failed to extract timezone info from the provided raw value.",
                tz_raw=tz_raw,
            )

        serializer = self.StructuredDateFilteringInfoSerializer(
            data={
                "preset": date_preset_raw,
                "custom_start": custom_date_start_raw,
                "custom_end": custom_date_end_raw,
            }
        )
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            raise ValueError("Invalid structured date filtering info.") from e
        validated_data = serializer.validated_data
        date_preset: Literal[
            "all",
            "today",
            "yesterday",
            "last3d",
            "last7d",
            "last30d",
            "custom",
        ] = validated_data["preset"]
        custom_date_start: date | None = validated_data.get("custom_start")
        custom_date_end: date | None = validated_data.get("custom_end")
        if date_preset == "custom":
            assert custom_date_start is not None, "Current pre-condition"
            assert custom_date_end is not None, "Current pre-condition"
            assert custom_date_end >= custom_date_start, "Current pre-condition"

        now_tz_aware = self.now.astimezone(zone_info)
        today_in_tz = now_tz_aware.date()

        td = timedelta
        td1 = td(days=1)
        td2 = td(days=2)
        td6 = td(days=6)
        td29 = td(days=29)

        d_start: date
        d_end: date
        dt_start: datetime
        dt_end: datetime
        if date_preset == "all":
            d_start = date.min
            d_end = date.max
            dt_start = datetime.combine(date.min, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(date.max, time.max, tzinfo=zone_info)
        elif date_preset == "today":
            d_start = today_in_tz
            d_end = today_in_tz
            dt_start = datetime.combine(today_in_tz, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(today_in_tz, time.max, tzinfo=zone_info)
        elif date_preset == "yesterday":
            d_start = today_in_tz - td1
            d_end = today_in_tz - td1
            dt_start = datetime.combine(today_in_tz - td1, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(today_in_tz - td1, time.max, tzinfo=zone_info)
        elif date_preset == "last3d":
            d_start = today_in_tz - td2
            d_end = today_in_tz
            dt_start = datetime.combine(today_in_tz - td2, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(today_in_tz, time.max, tzinfo=zone_info)
        elif date_preset == "last7d":
            d_start = today_in_tz - td6
            d_end = today_in_tz
            dt_start = datetime.combine(today_in_tz - td6, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(today_in_tz, time.max, tzinfo=zone_info)
        elif date_preset == "last30d":
            d_start = today_in_tz - td29
            d_end = today_in_tz
            dt_start = datetime.combine(today_in_tz - td29, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(today_in_tz, time.max, tzinfo=zone_info)
        elif date_preset == "custom":
            assert custom_date_start is not None, "Current pre-condition"
            assert custom_date_end is not None, "Current pre-condition"
            d_start = custom_date_start
            d_end = custom_date_end
            dt_start = datetime.combine(custom_date_start, time.min, tzinfo=zone_info)
            dt_end = datetime.combine(custom_date_end, time.max, tzinfo=zone_info)
        else:
            raise NotImplementedError(f"Unexpected preset value: `{date_preset}`.")

        structured_info = self.StructuredDateFilteringInfo(
            date_field_name=date_field_name,
            tz=zone_info,
            date_preset=date_preset,
            custom_date_start=custom_date_start,
            custom_date_end=custom_date_end,
            date_start=d_start,
            date_end=d_end,
            datetime_start=dt_start,
            datetime_end=dt_end,
        )
        if structured_info.custom_date_start and structured_info.custom_date_end:
            assert (
                structured_info.custom_date_start <= structured_info.custom_date_end
            ), "Current pre-condition"
        assert structured_info.date_start <= structured_info.date_end, (
            "Current pre-condition"
        )
        assert structured_info.datetime_start <= structured_info.datetime_end, (
            "Current pre-condition"
        )

        return structured_info

    @property
    def now(self) -> datetime:
        if self._now is None or self._now == "default":
            self._now = timezone.now()
        return self._now  # type: ignore[return-value]

    @now.setter
    def now(self, value: datetime) -> None:
        self._now = value

    date_preset_to_label: Final[dict[str, str]] = {
        "all": "All",
        "today": "Today",
        "yesterday": "Yesterday",
        "last3d": "Last 3 Days",
        "last7d": "Last 7 Days",
        "last30d": "Last 30 Days",
        "custom": "Custom",
    }

    @dataclass(kw_only=True)
    class StructuredDateFilteringInfo:
        date_field_name: str
        tz: ZoneInfo | python_timezone
        date_preset: Literal[
            "all",
            "today",
            "yesterday",
            "last3d",
            "last7d",
            "last30d",
            "custom",
        ]
        custom_date_start: date | None
        custom_date_end: date | None
        date_start: date
        date_end: date
        datetime_start: datetime
        datetime_end: datetime

    class StructuredDateFilteringInfoSerializer(serializers.Serializer):
        preset = serializers.ChoiceField(
            choices=[
                ("all", "All"),
                ("today", "Today"),
                ("yesterday", "Yesterday"),
                ("last3d", "Last 3 Days"),
                ("last7d", "Last 7 Days"),
                ("last30d", "Last 30 Days"),
                ("custom", "Custom"),
            ],
            required=True,
        )
        custom_start = serializers.DateField(required=False, allow_null=True)
        custom_end = serializers.DateField(required=False, allow_null=True)

        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            validated_data = super().validate(attrs)

            preset = validated_data.get("preset")
            custom_start = validated_data.get("custom_start")
            custom_end = validated_data.get("custom_end")

            if preset == "custom":
                if not custom_start or not custom_end:
                    raise serializers.ValidationError(
                        "Both `custom_start` and `custom_end` must be provided when "
                        "`preset` is `custom`."
                    )
                if custom_start > custom_end:
                    raise serializers.ValidationError(
                        "`custom_start` must be less than or equal to `custom_end`."
                    )

            return validated_data
