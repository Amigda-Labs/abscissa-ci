from abscissa_ci.models import (
    DimensionChain,
    DimensionChainSegment,
    DimensionSurvey,
    PolygonTraverse,
    TraverseMove,
)
from abscissa_ci.calculators.dimension_stations import (
    chain_stations,
    survey_stations,
    validate_station_alignment,
)
from abscissa_ci.calculators.traverse_geometry import traverse_to_polygon


def make_chain(orientation, texts, spans_full_extent=True, side="unknown"):
    return DimensionChain(
        orientation=orientation,
        side=side,
        segments=[DimensionChainSegment(source_text=text) for text in texts],
        spans_full_extent=spans_full_extent,
    )


def make_traverse(moves, name="Floor", **kwargs):
    return PolygonTraverse(
        name=name,
        moves=[TraverseMove(direction=d, length_m=l) for d, l in moves],
        **kwargs,
    )


def test_full_chain_without_gaps_gives_prefix_stations():
    chain = make_chain("horizontal", ["5.00 m", "4.00 m", "7.00 m"])

    assert chain_stations(chain, 16) == [0, 5, 9, 16]


def test_vertical_chain_counts_down_from_the_top():
    # Listed top-to-bottom: 4.50, 4.50, 4.00 over a 13m extent.
    chain = make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"])

    assert chain_stations(chain, 13) == [0, 4, 8.5, 13]


def test_single_gap_is_filled_with_the_complement():
    chain = make_chain("horizontal", ["5.00 m", None, "7.00 m"])

    assert chain_stations(chain, 16) == [0, 5, 9, 16]


def test_multiple_gaps_keep_only_anchored_runs():
    chain = make_chain("horizontal", ["3.00 m", None, "2.00 m", None, "4.00 m"])

    assert chain_stations(chain, 20) == [0, 3, 16, 20]


def test_partial_chain_contributes_no_stations():
    chain = make_chain("horizontal", ["4.00 m"], spans_full_extent=False)

    assert chain_stations(chain, 16) is None


def test_chain_that_does_not_sum_contributes_no_stations():
    chain = make_chain("horizontal", ["5.00 m", "4.00 m", "8.00 m"])

    assert chain_stations(chain, 16) is None


def offset_cross_survey():
    return DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain("horizontal", ["5.00 m", None, "7.00 m"], side="top"),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"], side="left"),
        ],
    )


def test_survey_stations_merge_chains_per_axis():
    x_stations, y_stations = survey_stations(offset_cross_survey())

    assert x_stations == [0, 5, 9, 16]
    assert y_stations == [0, 4, 8.5, 13]


def test_correct_offset_cross_passes_station_alignment():
    moves = [
        ("E", 4), ("N", 4), ("E", 7), ("N", 4.5), ("W", 7), ("N", 4.5),
        ("W", 4), ("S", 4.5), ("W", 5), ("S", 4.5), ("E", 5), ("S", 4),
    ]
    polygon, errors = traverse_to_polygon(make_traverse(moves, name="Offset Cross"))

    assert errors == []
    assert validate_station_alignment([polygon], offset_cross_survey()) == []


def test_staircase_rearrangement_is_blocked_by_station_alignment():
    # Same printed segment multiset as the offset cross, same bounding box,
    # closes perfectly - but the corners are off the extension-line grid.
    # This exact shape previously passed closure, bounding, and coverage.
    moves = [
        ("E", 16), ("N", 4.5), ("W", 5), ("N", 4.5), ("W", 7), ("N", 4),
        ("W", 4), ("S", 13),
    ]
    polygon, errors = traverse_to_polygon(make_traverse(moves, name="Staircase"))

    assert errors == []
    errors = validate_station_alignment([polygon], offset_cross_survey())

    assert len(errors) == 2
    assert "x axis" in errors[0] and "11" in errors[0]
    assert "y axis" in errors[1] and "4.5" in errors[1] and "9" in errors[1]


def test_subtract_polygons_are_not_station_checked():
    void_moves = [("E", 2), ("N", 1.5), ("W", 2), ("S", 1.5)]
    polygon, errors = traverse_to_polygon(
        make_traverse(void_moves, name="Void", operation="subtract")
    )

    assert errors == []
    assert validate_station_alignment([polygon], offset_cross_survey()) == []


def test_axis_without_anchored_chain_is_not_checked():
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[make_chain("horizontal", ["5.00 m", None, "7.00 m"], side="top")],
    )
    moves = [("E", 16), ("N", 6.5), ("W", 16), ("S", 6.5)]
    polygon, errors = traverse_to_polygon(make_traverse(moves))

    assert errors == []
    # y=6.5 is off the cross's y grid, but no vertical chain was anchored.
    assert validate_station_alignment([polygon], survey) == []


def make_survey_entries(texts):
    from abscissa_ci.models import DimensionSurveyEntry

    return [DimensionSurveyEntry(source_text=text) for text in texts]


def test_validate_survey_passes_consistent_offset_cross():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=make_survey_entries(
            ["16.00 m", "13.00 m", "5.00 m", "7.00 m", "4.50 m", "4.50 m", "4.00 m", "4.00 m"]
        ),
        chains=[
            make_chain("horizontal", ["5.00 m", None, "7.00 m"], side="top"),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"], side="left"),
            make_chain("horizontal", ["4.00 m"], spans_full_extent=False, side="bottom"),
        ],
    )

    assert validate_survey(survey) == []


def test_validate_survey_flags_missing_bounding_dimensions():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    errors = validate_survey(DimensionSurvey())

    assert len(errors) == 2
    assert "bounding_width_m" in errors[0]
    assert "bounding_height_m" in errors[1]


def test_validate_survey_flags_full_chain_that_does_not_sum():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=make_survey_entries(["5.00 m", "7.00 m"]),
        chains=[make_chain("horizontal", ["5.00 m", "7.00 m"], side="top")],
    )

    errors = validate_survey(survey)

    assert len(errors) == 1
    assert "sums to 12m" in errors[0]


def test_validate_survey_flags_label_outside_any_chain():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=make_survey_entries(["16.00 m", "13.00 m", "5.00 m"]),
        chains=[],
    )

    errors = validate_survey(survey)

    assert len(errors) == 1
    assert "'5.00 m'" in errors[0]


def test_validate_survey_flags_double_listed_entry():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=make_survey_entries(["5.00 m", "5.00 m", None or "11.00 m"]),
        chains=[
            make_chain("horizontal", ["5.00 m", "11.00 m"], side="top"),
        ],
    )

    errors = validate_survey(survey)

    assert len(errors) == 1
    assert "'5.00 m'" in errors[0]


def test_validate_survey_flags_chain_segment_missing_from_entries():
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=make_survey_entries(["5.00 m"]),
        chains=[make_chain("horizontal", ["5.00 m", "11.00 m"], side="top")],
    )

    errors = validate_survey(survey)

    assert len(errors) == 1
    assert "'11.00 m'" in errors[0]


def test_partial_lane_is_promoted_when_axis_has_no_anchored_chain():
    # The model failed to mark the 5/gap/7 lane as full extent; with no other
    # anchored horizontal chain, the lane is promoted because its labels plus
    # one gap fill the 16m extent.
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain(
                "horizontal", ["5.00 m", None, "7.00 m"], spans_full_extent=False
            ),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"], side="left"),
        ],
    )

    x_stations, y_stations = survey_stations(survey)

    assert x_stations == [0, 5, 9, 16]
    assert y_stations == [0, 4, 8.5, 13]


def test_single_segment_partial_lane_is_not_promoted():
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain("horizontal", ["4.00 m"], spans_full_extent=False),
        ],
    )

    x_stations, _ = survey_stations(survey)

    assert x_stations is None


def test_partial_lane_that_cannot_fill_the_extent_is_not_promoted():
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain("horizontal", ["5.00 m", "7.00 m"], spans_full_extent=False),
        ],
    )

    x_stations, _ = survey_stations(survey)

    assert x_stations is None


def test_anchored_chain_suppresses_promotion_on_its_axis():
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain("horizontal", ["9.00 m", "7.00 m"], spans_full_extent=True),
            make_chain(
                "horizontal", ["5.00 m", None, "7.00 m"], spans_full_extent=False
            ),
        ],
    )

    x_stations, _ = survey_stations(survey)

    assert x_stations == [0, 9, 16]


def make_anchored_chain(orientation, texts, starts=False, ends=False):
    return DimensionChain(
        orientation=orientation,
        segments=[DimensionChainSegment(source_text=text) for text in texts],
        starts_at_outline_edge=starts,
        ends_at_outline_edge=ends,
    )


def test_chain_anchored_at_start_contributes_prefix_stations():
    chain = make_anchored_chain("horizontal", ["5.00 m"], starts=True)

    assert chain_stations(chain, 16) == [0, 5]


def test_chain_anchored_at_end_contributes_suffix_stations():
    chain = make_anchored_chain("horizontal", ["7.00 m"], ends=True)

    assert chain_stations(chain, 16) == [9, 16]


def test_unanchored_chain_contributes_no_stations():
    chain = make_anchored_chain("horizontal", ["4.00 m"])

    assert chain_stations(chain, 16) is None


def test_disjoint_anchored_lanes_assemble_the_full_grid():
    # The offset cross drawn honestly: 5.00 anchored at the left edge, 7.00
    # anchored at the right edge, left vertical chain spanning the height.
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_anchored_chain("horizontal", ["5.00 m"], starts=True),
            make_anchored_chain("horizontal", ["7.00 m"], ends=True),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"]),
        ],
    )

    x_stations, y_stations = survey_stations(survey)

    assert x_stations == [0, 5, 9, 16]
    assert y_stations == [0, 4, 8.5, 13]


def test_vertical_chain_anchored_at_top_counts_down():
    # Listed top-to-bottom and anchored at the topmost point: 4.50 from the
    # top of a 13m extent marks y stations 13 and 8.5.
    chain = make_anchored_chain("vertical", ["4.50 m"], starts=True)

    assert chain_stations(chain, 13) == [8.5, 13]


def test_anchored_prefix_overflowing_the_extent_is_rejected():
    chain = make_anchored_chain("horizontal", ["9.00 m", "8.00 m"], starts=True)

    assert chain_stations(chain, 16) is None


def test_overall_only_chain_does_not_suppress_promotion():
    # The 16.00 overall chain yields only {0, 16}; the unanchored 5/gap/7
    # lane must still be promoted to supply the interior stations.
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        chains=[
            make_chain("horizontal", ["16.00 m"], side="top"),
            make_chain(
                "horizontal", ["5.00 m", None, "7.00 m"], spans_full_extent=False
            ),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"], side="left"),
        ],
    )

    x_stations, y_stations = survey_stations(survey)

    assert x_stations == [0, 5, 9, 16]
    assert y_stations == [0, 4, 8.5, 13]


def test_validate_survey_flags_unpinned_segment_labels():
    from abscissa_ci.models import DimensionSurveyEntry
    from abscissa_ci.calculators.dimension_stations import validate_survey

    # 5.00 and 7.00 reported as separate unanchored single-segment lanes:
    # consistent bookkeeping, but the axis grid stays unusable.
    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=[
            DimensionSurveyEntry(source_text="16.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="13.00 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="5.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="7.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="4.50 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="4.50 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="4.00 m", orientation="vertical"),
        ],
        chains=[
            make_anchored_chain("horizontal", ["5.00 m"]),
            make_anchored_chain("horizontal", ["7.00 m"]),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"]),
        ],
    )

    errors = validate_survey(survey)

    assert len(errors) == 1
    assert "Horizontal segment labels" in errors[0]


def test_validate_survey_accepts_anchored_disjoint_lanes():
    from abscissa_ci.models import DimensionSurveyEntry
    from abscissa_ci.calculators.dimension_stations import validate_survey

    survey = DimensionSurvey(
        bounding_width_m=16,
        bounding_height_m=13,
        entries=[
            DimensionSurveyEntry(source_text="16.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="13.00 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="5.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="7.00 m", orientation="horizontal"),
            DimensionSurveyEntry(source_text="4.50 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="4.50 m", orientation="vertical"),
            DimensionSurveyEntry(source_text="4.00 m", orientation="vertical"),
        ],
        chains=[
            make_anchored_chain("horizontal", ["5.00 m"], starts=True),
            make_anchored_chain("horizontal", ["7.00 m"], ends=True),
            make_chain("vertical", ["4.50 m", "4.50 m", "4.00 m"]),
        ],
    )

    assert validate_survey(survey) == []


def test_interval_matched_entries_are_filtered():
    from abscissa_ci.calculators.dimension_stations import (
        filter_interval_matched_entries,
    )

    # Void margins 5.50/3.50 and void spans 5/3 are station intervals; the
    # 99.00 label matches nothing and stays for coverage to flag.
    remaining = filter_interval_matched_entries(
        ["5.50 m", "5.50 m", "3.50 m", "5.00 m", "3.00 m", "99.00 m"],
        [0, 5.5, 10.5, 16],
        [0, 3.5, 6.5, 10],
    )

    assert remaining == ["99.00 m"]


def test_unused_interior_station_is_flagged():
    from abscissa_ci.calculators.dimension_stations import validate_station_usage
    from abscissa_ci.models import PolygonDraft, PolygonPoint

    # A shape spanning the grid but with no corner at interior station y=8.5.
    polygon = PolygonDraft(
        points=[
            PolygonPoint(x_m=0, y_m=0),
            PolygonPoint(x_m=16, y_m=0),
            PolygonPoint(x_m=16, y_m=13),
            PolygonPoint(x_m=0, y_m=13),
        ]
    )

    errors = validate_station_usage([polygon], [0, 16], [0, 4, 8.5, 13])

    assert len(errors) == 2
    assert "y station 4m" in errors[0]
    assert "y station 8.5m" in errors[1]


def test_void_corner_counts_as_station_usage():
    from abscissa_ci.calculators.dimension_stations import validate_station_usage
    from abscissa_ci.models import PolygonDraft, PolygonPoint

    outer = PolygonDraft(
        points=[
            PolygonPoint(x_m=0, y_m=0),
            PolygonPoint(x_m=16, y_m=0),
            PolygonPoint(x_m=16, y_m=10),
            PolygonPoint(x_m=0, y_m=10),
        ]
    )
    void = PolygonDraft(
        operation="subtract",
        points=[
            PolygonPoint(x_m=5.5, y_m=3.5),
            PolygonPoint(x_m=10.5, y_m=3.5),
            PolygonPoint(x_m=10.5, y_m=6.5),
            PolygonPoint(x_m=5.5, y_m=6.5),
        ],
    )

    errors = validate_station_usage(
        [outer, void], [0, 5.5, 10.5, 16], [0, 3.5, 6.5, 10]
    )

    assert errors == []
