from app.matching import MAX_DISTANCE_KM, W_INTENSITY, W_SPORT, find_matches, score_pair
from app.models import Profile, ProfileSport


def make(pid, sports, lat=50.45, lon=30.52, intensity=3, visible=True):
    p = Profile(
        id=pid,
        display_name=pid,
        district=None,
        area_lat=lat,
        area_lon=lon,
        intensity=intensity,
        is_visible=visible,
    )
    p.sports = [ProfileSport(sport=s) for s in sports]
    return p


def test_no_shared_sport_gives_zero():
    a, b = make("a", ["swimming"]), make("b", ["archery"])
    assert score_pair(a, b)[0] == 0


def test_identical_profiles_give_maximum():
    a, b = make("a", ["swimming"]), make("b", ["swimming"])
    assert score_pair(a, b)[0] == 100


def test_score_decreases_with_distance():
    me = make("me", ["swimming"])
    near = make("n", ["swimming"], lat=50.46)
    far = make("f", ["swimming"], lat=50.60)
    assert score_pair(me, near)[0] > score_pair(me, far)[0]


def test_score_decreases_with_intensity_gap():
    me = make("me", ["swimming"], intensity=3)
    close = make("c", ["swimming"], intensity=3)
    gap = make("g", ["swimming"], intensity=5)
    assert score_pair(me, close)[0] > score_pair(me, gap)[0]


def test_matches_exclude_self_hidden_and_unrelated_and_are_sorted():
    me = make("me", ["swimming"])
    best = make("best", ["swimming"])
    worse = make("worse", ["swimming", "archery"], intensity=1)
    hidden = make("hidden", ["swimming"], visible=False)
    other = make("other", ["archery"])
    result = find_matches(me, [me, best, worse, hidden, other], limit=10)
    assert [m.profile.id for m in result] == ["best", "worse"]


def test_limit_applies():
    me = make("me", ["swimming"])
    others = [make(f"p{i}", ["swimming"]) for i in range(5)]
    assert len(find_matches(me, others, limit=3)) == 3


def test_distance_part_is_zero_beyond_max_distance_but_other_parts_remain():
    me = make("me", ["swimming"])
    # 0.5° of latitude ≈ 55 km, which is more than MAX_DISTANCE_KM
    far = make("far", ["swimming"], lat=50.95)
    score, km = score_pair(me, far)
    assert km >= MAX_DISTANCE_KM
    assert score == W_SPORT + W_INTENSITY


def test_equal_scores_are_ordered_by_id():
    me = make("me", ["swimming"])
    others = [make(pid, ["swimming"]) for pid in ("c", "a", "d", "b")]
    result = find_matches(me, others, limit=10)
    assert len({m.score for m in result}) == 1
    assert [m.profile.id for m in result] == ["a", "b", "c", "d"]
    reverse = find_matches(me, list(reversed(others)), limit=10)
    assert [m.profile.id for m in reverse] == ["a", "b", "c", "d"]
