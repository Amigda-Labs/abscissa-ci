from abscissa_ci.cad.models import Point, WallSegment
from abscissa_ci.cad.wall_geometry import point_key, wall_joint_polygons, wall_solid_polygon


def test_wall_solid_polygon_keeps_free_ends_square_on_centerline_endpoints() -> None:
    wall = WallSegment(
        wall_id="w1",
        start=Point(x=0, y=0),
        end=Point(x=2, y=0),
        wall_type="interior",
        thickness_mm=100,
    )

    solid = wall_solid_polygon(wall)

    assert [(point.x, point.y) for point in solid.points] == [
        (0, 0.05),
        (2, 0.05),
        (2, -0.05),
        (0, -0.05),
    ]


def test_wall_joint_polygon_closes_orthogonal_l_corner() -> None:
    walls = [
        WallSegment(
            wall_id="horizontal",
            start=Point(x=0, y=0),
            end=Point(x=2, y=0),
            wall_type="exterior",
            thickness_mm=150,
        ),
        WallSegment(
            wall_id="vertical",
            start=Point(x=2, y=0),
            end=Point(x=2, y=2),
            wall_type="exterior",
            thickness_mm=150,
        ),
    ]

    joints = wall_joint_polygons(walls)

    assert len(joints) == 1
    assert joints[0].wall_ids == ["horizontal", "vertical"]
    assert joints[0].wall_type == "exterior"
    assert [(point.x, point.y) for point in joints[0].points] == [
        (1.925, -0.075),
        (2.075, -0.075),
        (2.075, 0.075),
        (1.925, 0.075),
    ]


def test_wall_joint_polygon_skips_suppressed_door_gap_endpoints() -> None:
    walls = [
        WallSegment(
            wall_id="horizontal",
            start=Point(x=0, y=0),
            end=Point(x=2, y=0),
            wall_type="interior",
            thickness_mm=100,
        ),
        WallSegment(
            wall_id="vertical",
            start=Point(x=2, y=0),
            end=Point(x=2, y=2),
            wall_type="interior",
            thickness_mm=100,
        ),
    ]

    joints = wall_joint_polygons(walls, suppressed_endpoint_keys={point_key(Point(x=2, y=0))})

    assert joints == []
