"""Smoke checks for the Muntanga map's stable selection and grade labeling."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'frontend/muntanga_exploration_view.py'
CHART = ROOT / 'frontend/muntanga_linked_chart.py'


def test_picking_layer_retains_existing_selection_id():
    source = VIEW.read_text(encoding='utf-8')
    assert 'id="muntanga-north-collars",' in source
    assert 'id="muntanga-north-collars-visible",' in source
    assert 'layers=[selection_layer, visual_layer]' in source
    assert 'radius_min_pixels=14' in source
    assert 'radius_max_pixels=14' in source
    assert 'pickable=False' in source


def test_linked_profile_and_no_intercept_guards_remain():
    view = VIEW.read_text(encoding='utf-8')
    chart = CHART.read_text(encoding='utf-8')
    assert 'selected_collar_id = render_collar_inspector' in view
    assert 'render_linked_depth_profile(report, selected_collar_id, placement="intervals")' in view
    assert 'not establish a zero uranium grade' in chart


def test_uranium_legend_uses_human_readable_numbers():
    view = VIEW.read_text(encoding='utf-8')
    chart = CHART.read_text(encoding='utf-8')
    assert 'legend=alt.Legend(format=",.0f")' in view
    assert 'legend=alt.Legend(format=",.0f", tickCount=4)' in chart
    assert 'alt.Tooltip("eU3O8 (ppm):Q", format=",.0f")' in chart
