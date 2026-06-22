from abscissa_ci.cad.door_style import load_door_style


def test_door_style_loads_shared_defaults() -> None:
    style = load_door_style()

    assert style.frame_jamb_mm == 50
    assert style.leaf_thickness_mm == 45
    assert style.leaf_width_mm.exterior == 900
    assert style.leaf_width_mm.interior == 800


def test_door_style_opening_width_includes_two_jambs() -> None:
    style = load_door_style()

    # 900 mm leaf + 2 x 50 mm jamb = 1000 mm framed opening.
    assert style.opening_width_m_for_wall_type("exterior") == 1.0
    # 800 mm leaf + 2 x 50 mm jamb = 900 mm framed opening.
    assert round(style.opening_width_m_for_wall_type("interior"), 6) == 0.9
