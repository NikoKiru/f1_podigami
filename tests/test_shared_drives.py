"""The rules for expanding a shared-car podium into driver trios."""

from compute.shared_drives import (
    has_shared_drive,
    podium_drivers,
    podium_trios,
    slot_drivers,
)


def _ref(did):
    return {"driverId": did, "name": did.title()}


NORMAL = {
    "season": "2021",
    "round": "21",
    "raceName": "Saudi Arabian Grand Prix",
    "p1": _ref("hamilton"),
    "p2": _ref("max_verstappen"),
    "p3": _ref("bottas"),
}

# 1956 Belgium: Perdisa and Moss shared the third-placed Maserati.
BELGIUM_1956 = {
    "season": "1956",
    "round": "4",
    "raceName": "Belgian Grand Prix",
    "p1": _ref("collins"),
    "p2": _ref("frere"),
    "p3": _ref("perdisa"),
    "coDrivers": {"p3": [_ref("moss")]},
}

# 1955 Argentina: Farina and Trintignant each drove a share of BOTH the
# second- and third-placed cars, so they appear at two positions at once.
ARGENTINA_1955 = {
    "season": "1955",
    "round": "1",
    "raceName": "Argentine Grand Prix",
    "p1": _ref("fangio"),
    "p2": _ref("farina"),
    "p3": _ref("maglioli"),
    "coDrivers": {
        "p2": [_ref("gonzalez"), _ref("trintignant")],
        "p3": [_ref("farina"), _ref("trintignant")],
    },
}


def test_normal_race_is_not_shared():
    assert has_shared_drive(NORMAL) is False
    assert slot_drivers(NORMAL, "p3") == [_ref("bottas")]
    assert podium_trios(NORMAL) == [("bottas", "hamilton", "max_verstappen")]


def test_shared_step_yields_both_trios():
    assert has_shared_drive(BELGIUM_1956) is True
    assert [d["driverId"] for d in slot_drivers(BELGIUM_1956, "p3")] == ["perdisa", "moss"]
    assert podium_trios(BELGIUM_1956) == [
        ("collins", "frere", "moss"),
        ("collins", "frere", "perdisa"),
    ]


def test_podium_drivers_lists_everyone_once():
    assert [d["driverId"] for d in podium_drivers(BELGIUM_1956)] == [
        "collins",
        "frere",
        "perdisa",
        "moss",
    ]
    # farina and trintignant sit at two positions but are one driver each
    assert [d["driverId"] for d in podium_drivers(ARGENTINA_1955)] == [
        "fangio",
        "farina",
        "gonzalez",
        "trintignant",
        "maglioli",
    ]


def test_a_driver_never_appears_twice_in_one_trio():
    trios = podium_trios(ARGENTINA_1955)
    for t in trios:
        assert len(set(t)) == 3, f"{t} names a driver twice"
    assert trios == sorted(set(trios)), "trios must be sorted and deduplicated"
    # fangio + (farina|gonzalez|trintignant) + (maglioli|farina|trintignant),
    # minus the two products that name farina or trintignant twice. Six survive
    # — including fangio/farina/gonzalez, which is real: gonzalez drove a share
    # of the second-placed car and farina a share of the third.
    assert trios == [
        ("fangio", "farina", "gonzalez"),
        ("fangio", "farina", "maglioli"),
        ("fangio", "farina", "trintignant"),
        ("fangio", "gonzalez", "maglioli"),
        ("fangio", "gonzalez", "trintignant"),
        ("fangio", "maglioli", "trintignant"),
    ]
