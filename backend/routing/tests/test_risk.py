# tests for the risk classifier. these are the spec's tables turned into asserts.

from django.test import TestCase
from routing.risk import classify_risk, band, WIND_BANDS, RAIN_BANDS, SNOW_BANDS


# calm baseline so each test only varies the thing it cares about
CALM = dict(wind_mph=10, rain_in_hr=0.0, snow_in_hr=0.0, load_lb=10000)


def risk(**overrides):
    args = {**CALM, **overrides}
    return classify_risk(args["wind_mph"], args["rain_in_hr"], args["snow_in_hr"], args["load_lb"])


class BandBoundaryTests(TestCase):
    """the exact numbers from the spec. this is where off-by-one bugs live."""

    def test_wind_bands(self):
        # low < 25
        self.assertEqual(risk(wind_mph=24.9), "LOW")
        # 25-34 moderate
        self.assertEqual(risk(wind_mph=25), "MODERATE")
        self.assertEqual(risk(wind_mph=34.9), "MODERATE")
        # 35-44 high
        self.assertEqual(risk(wind_mph=35), "HIGH")
        self.assertEqual(risk(wind_mph=44.9), "HIGH")
        # 45-54 severe
        self.assertEqual(risk(wind_mph=45), "SEVERE")
        self.assertEqual(risk(wind_mph=54.9), "SEVERE")
        # >=55 no travel
        self.assertEqual(risk(wind_mph=55), "NO_TRAVEL")

    def test_rain_bands_are_strict_at_the_top(self):
        # spec says >1.00 for no travel, so 1.00 exactly stays severe
        self.assertEqual(risk(rain_in_hr=0.09), "LOW")
        self.assertEqual(risk(rain_in_hr=0.10), "MODERATE")
        self.assertEqual(risk(rain_in_hr=0.50), "SEVERE")
        self.assertEqual(risk(rain_in_hr=1.00), "SEVERE")
        self.assertEqual(risk(rain_in_hr=1.01), "NO_TRAVEL")

    def test_snow_bands(self):
        self.assertEqual(risk(snow_in_hr=0.49), "LOW")
        self.assertEqual(risk(snow_in_hr=0.5), "MODERATE")
        self.assertEqual(risk(snow_in_hr=1.0), "HIGH")
        self.assertEqual(risk(snow_in_hr=3.0), "SEVERE")
        self.assertEqual(risk(snow_in_hr=3.01), "NO_TRAVEL")


class WorstOfTests(TestCase):
    """the classifier should return the worst of the three conditions."""

    def test_rain_beats_calm_wind(self):
        self.assertEqual(risk(wind_mph=10, rain_in_hr=0.30), "HIGH")

    def test_snow_beats_wind(self):
        self.assertEqual(risk(wind_mph=10, snow_in_hr=1.5), "HIGH")

    def test_worst_wins(self):
        self.assertEqual(risk(wind_mph=50, rain_in_hr=0.30, snow_in_hr=0.0), "SEVERE")


class LoadEscalationTests(TestCase):
    """load rules only escalate. they must never de-escalate a worse base risk."""

    def test_any_load_at_55mph_is_no_travel(self):
        self.assertEqual(risk(wind_mph=55, load_lb=5000), "NO_TRAVEL")

    def test_heavy_load_at_45mph_is_no_travel(self):
        # 45-54 + >30000 lb -> no travel
        self.assertEqual(risk(wind_mph=45, load_lb=30001), "NO_TRAVEL")

    def test_light_load_at_45mph_stays_severe(self):
        # not heavy enough, so base wind band (severe) applies
        self.assertEqual(risk(wind_mph=45, load_lb=30000), "SEVERE")

    def test_heavy_load_at_40mph_is_severe(self):
        # 35-44 + >40000 lb -> severe
        self.assertEqual(risk(wind_mph=40, load_lb=40001), "SEVERE")

    def test_boundary_load_at_40mph_stays_high(self):
        # exactly 40000 is not >40000
        self.assertEqual(risk(wind_mph=40, load_lb=40000), "HIGH")

    def test_load_escalation_does_not_override_no_travel_from_rain(self):
        # this is the bug we caught earlier. rain is already no-travel,
        # wind load rule would say severe but no travel must win.
        self.assertEqual(
            risk(wind_mph=40, rain_in_hr=1.5, load_lb=45000),
            "NO_TRAVEL",
        )