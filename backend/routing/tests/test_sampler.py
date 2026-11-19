from django.test import TestCase
from routing.sampler import sample_route, haversine_m, METERS_PER_MILE


# a dead-straight north-south line. 1 degree of latitude is ~111 km
# so this route is roughly 69 miles. handy for predictable math.
# (lon, lat) pairs, matching ORS geojson order
STRAIGHT = [
    [-100.0, 40.0],
    [-100.0, 40.5],
    [-100.0, 41.0],
]


class SamplerTests(TestCase):

    def test_haversine_sanity(self):
        # two points 1 degree of lat apart should be ~111 km
        d = haversine_m([0, 0], [0, 1])
        self.assertAlmostEqual(d, 111195, delta=2000)

    def test_start_and_end_always_included(self):
        # even if the interval is huge, we should get start + end at minimum
        cps = sample_route(STRAIGHT, [111000], [3600], interval_mi=500)
        self.assertGreaterEqual(len(cps), 2)
        self.assertAlmostEqual(cps[0]["distance_mi"], 0.0, places=3)
        # last checkpoint should be the total distance
        total_mi = cps[-1]["distance_mi"]
        self.assertGreater(total_mi, 60)

    def test_interval_respected(self):
        # ~69 mi route, 25 mi interval -> should land near 0, 25, 50, then endpoint
        cps = sample_route(STRAIGHT, [111000], [3600], interval_mi=25)

        distances = [c["distance_mi"] for c in cps]

        # first is the start
        self.assertAlmostEqual(distances[0], 0.0, places=3)

        # every consecutive gap should be at most the interval
        # (last gap can be a partial one, that's fine)
        for i in range(1, len(distances)):
            gap = distances[i] - distances[i - 1]
            self.assertLessEqual(gap, 25 + 0.01)  # tiny slop for float math
            self.assertGreater(gap, 0)

        # we expect 4 checkpoints on a 69 mi route: 0, 25, 50, ~69
        self.assertEqual(len(distances), 4)

        # the checkpoints we asked for should be close to where we wanted them
        self.assertAlmostEqual(distances[1], 25.0, places=1)
        self.assertAlmostEqual(distances[2], 50.0, places=1)