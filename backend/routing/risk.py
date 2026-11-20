# risk.py - the core logic. everything downstream depends on this being right.

# band boundaries. spec is literal about these so dont "fix" the asymmetry
WIND_BANDS = [25, 35, 45, 55]            # >=55 is no travel
RAIN_BANDS = [0.10, 0.25, 0.50, 1.00]    # >1.00 is no travel (note: > not >=, spec says so)
SNOW_BANDS = [0.5, 1.0, 2.0, 3.0]        # >3.0 no travel

RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "SEVERE", "NO_TRAVEL"]


def band(value, thresholds, is_top_inclusive):
    """
    returns index into RISK_LEVELS based on which band the value falls in.
    0=low ... 4=no travel.
    is_top_inclusive controls the last band: wind is >=, rain/snow are >.
    """
    if value is None:
        return None  # caller deals with missing data, we dont guess here

    for i, t in enumerate(thresholds):
        if value < t:
            return i  # fell into the band before this threshold

    # past all thresholds -> top band. but > vs >= matters
    last = thresholds[-1]
    if is_top_inclusive:
        return 4 if value >= last else 3
    else:
        return 4 if value > last else 3


def classify_risk(wind_mph, rain_in_hr, snow_in_hr, load_lb):
    """
    Returns one of RISK_LEVELS. Worst-of wind/rain/snow, then load escalation.
    Load rules only touch wind per spec - rain/snow stay as base table says.
    """
    # TODO: what if all three are None? right now we'd treat them as low. handle at caller.
    wind_i = band(wind_mph, WIND_BANDS, is_top_inclusive=True)
    rain_i = band(rain_in_hr, RAIN_BANDS, is_top_inclusive=False)
    snow_i = band(snow_in_hr, SNOW_BANDS, is_top_inclusive=False)

    # missing values -> treat as low for now, flag at caller level.
    # ugly but keeps this function total instead of blowing up on None.
    base = max(
        0 if wind_i is None else wind_i,
        0 if rain_i is None else rain_i,
        0 if snow_i is None else snow_i,
    )

    # load escalation. ONLY escalates, never de-escalates.
    load_i = 0
    if wind_mph is not None:
        if wind_mph >= 55:
            load_i = 4
        elif 45 <= wind_mph < 55 and load_lb and load_lb > 30000:
            load_i = 4
        elif 35 <= wind_mph < 45 and load_lb and load_lb > 40000:
            load_i = 3  # severe, not no-travel

    final_i = max(base, load_i)



    return RISK_LEVELS[final_i]