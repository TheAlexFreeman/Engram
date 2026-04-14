from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from time_machine import TimeMachineFixture

from backend.utils.date_filters import DateFilterOps


def test_extract_structured_date_filtering_info(
    settings, time_machine: TimeMachineFixture
):
    tz_new_york = ZoneInfo("America/New_York")
    assert tz_new_york, "Pre-condition"
    tz_los_angeles = ZoneInfo("America/Los_Angeles")
    assert tz_los_angeles, "Pre-condition"
    tz_utc1 = ZoneInfo(settings.TIME_ZONE)
    tz_utc2 = UTC
    ny_datetime1 = datetime(2024, 6, 17, 22, 12, 18, tzinfo=tz_new_york)
    la_datetime1 = datetime(2024, 6, 14, 22, 12, 19, tzinfo=tz_los_angeles)
    utc_datetime1 = datetime(2024, 6, 15, 5, 37, 21, tzinfo=tz_utc1)

    v_ops1 = DateFilterOps(set_now_to=ny_datetime1)

    extracted1 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted1 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 17),
        date_end=date(2024, 6, 17),
        datetime_start=datetime(2024, 6, 17, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 17, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    extracted2 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="yesterday",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted2 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="yesterday",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 16),
        date_end=date(2024, 6, 16),
        datetime_start=datetime(2024, 6, 16, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 16, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    extracted3 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="last3d",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted3 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="last3d",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 15),
        date_end=date(2024, 6, 17),
        datetime_start=datetime(2024, 6, 15, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 17, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    extracted4 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="last7d",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted4 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="last7d",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 11),
        date_end=date(2024, 6, 17),
        datetime_start=datetime(2024, 6, 11, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 17, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    extracted5 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="last30d",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted5 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="last30d",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 5, 19),
        date_end=date(2024, 6, 17),
        datetime_start=datetime(2024, 5, 19, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 17, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    extracted6 = v_ops1.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="custom",
        custom_date_start_raw="2024-06-09",
        custom_date_end_raw="2024-06-14",
    )
    assert extracted6 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="custom",
        custom_date_start=date(2024, 6, 9),
        custom_date_end=date(2024, 6, 14),
        date_start=date(2024, 6, 9),
        date_end=date(2024, 6, 14),
        datetime_start=datetime(2024, 6, 9, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 14, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )

    time_machine.move_to(la_datetime1, tick=False)
    v_ops2 = DateFilterOps()

    extracted7 = v_ops2.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/Los_Angeles",
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted7 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/Los_Angeles"),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 14),
        date_end=date(2024, 6, 14),
        datetime_start=datetime(2024, 6, 14, 0, 0, 0, tzinfo=tz_los_angeles),
        datetime_end=datetime(2024, 6, 14, 23, 59, 59, 999999, tzinfo=tz_los_angeles),
    )

    extracted8 = v_ops2.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/Los_Angeles",
        date_preset_raw="last3d",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted8 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/Los_Angeles"),
        date_preset="last3d",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 12),
        date_end=date(2024, 6, 14),
        datetime_start=datetime(2024, 6, 12, 0, 0, 0, tzinfo=tz_los_angeles),
        datetime_end=datetime(2024, 6, 14, 23, 59, 59, 999999, tzinfo=tz_los_angeles),
    )

    time_machine.move_to(utc_datetime1)
    v_ops3 = DateFilterOps()

    extracted9 = v_ops3.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw=settings.TIME_ZONE,
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    extracted10 = v_ops3.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="UTC",
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    extracted11 = v_ops3.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/Los_Angeles",
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    extracted12 = v_ops3.extract_structured_date_filtering_info(
        date_field_name="duck",
        tz_raw="America/New_York",
        date_preset_raw="today",
        custom_date_start_raw=None,
        custom_date_end_raw=None,
    )
    assert extracted9 == extracted10
    assert extracted9 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo(settings.TIME_ZONE),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 15),
        date_end=date(2024, 6, 15),
        datetime_start=datetime(2024, 6, 15, 0, 0, 0, tzinfo=tz_utc1),
        datetime_end=datetime(2024, 6, 15, 23, 59, 59, 999999, tzinfo=tz_utc1),
    )
    assert extracted10 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo(settings.TIME_ZONE),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 15),
        date_end=date(2024, 6, 15),
        datetime_start=datetime(2024, 6, 15, 0, 0, 0, tzinfo=tz_utc2),
        datetime_end=datetime(2024, 6, 15, 23, 59, 59, 999999, tzinfo=tz_utc2),
    )
    assert extracted11 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/Los_Angeles"),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 14),
        date_end=date(2024, 6, 14),
        datetime_start=datetime(2024, 6, 14, 0, 0, 0, tzinfo=tz_los_angeles),
        datetime_end=datetime(2024, 6, 14, 23, 59, 59, 999999, tzinfo=tz_los_angeles),
    )
    assert extracted12 == DateFilterOps.StructuredDateFilteringInfo(
        date_field_name="duck",
        tz=ZoneInfo("America/New_York"),
        date_preset="today",
        custom_date_start=None,
        custom_date_end=None,
        date_start=date(2024, 6, 15),
        date_end=date(2024, 6, 15),
        datetime_start=datetime(2024, 6, 15, 0, 0, 0, tzinfo=tz_new_york),
        datetime_end=datetime(2024, 6, 15, 23, 59, 59, 999999, tzinfo=tz_new_york),
    )
