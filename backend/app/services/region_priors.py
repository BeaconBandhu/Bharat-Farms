"""Static state -> typical crops table.

A sanity fallback / cross-check for the satellite + AI crop inference. Not
exhaustive; covers major producing states. Keys are lowercase Nominatim
"state" strings.
"""
from __future__ import annotations

_PRIORS: dict[str, dict[str, list[str]]] = {
    "punjab": {"kharif": ["Rice", "Cotton", "Maize"], "rabi": ["Wheat", "Mustard", "Potato"]},
    "haryana": {"kharif": ["Rice", "Cotton", "Bajra"], "rabi": ["Wheat", "Mustard", "Barley"]},
    "uttar pradesh": {"kharif": ["Rice", "Sugarcane", "Maize"], "rabi": ["Wheat", "Mustard", "Potato"]},
    "madhya pradesh": {"kharif": ["Soybean", "Maize", "Cotton"], "rabi": ["Wheat", "Gram", "Mustard"]},
    "maharashtra": {"kharif": ["Cotton", "Soybean", "Rice", "Tur"], "rabi": ["Jowar", "Wheat", "Gram", "Onion"]},
    "gujarat": {"kharif": ["Cotton", "Groundnut", "Bajra"], "rabi": ["Wheat", "Cumin", "Mustard"]},
    "rajasthan": {"kharif": ["Bajra", "Guar", "Moong", "Groundnut"], "rabi": ["Wheat", "Mustard", "Gram"]},
    "karnataka": {"kharif": ["Maize", "Cotton", "Tur", "Ragi", "Sugarcane"], "rabi": ["Jowar", "Bengal Gram", "Sunflower"]},
    "andhra pradesh": {"kharif": ["Rice", "Cotton", "Groundnut", "Chilli"], "rabi": ["Rice", "Bengal Gram", "Maize"]},
    "telangana": {"kharif": ["Rice", "Cotton", "Maize", "Soybean"], "rabi": ["Rice", "Bengal Gram", "Groundnut"]},
    "tamil nadu": {"kharif": ["Rice", "Groundnut", "Cotton"], "rabi": ["Rice", "Pulses", "Maize"], "extra": ["Sugarcane", "Banana", "Turmeric"]},
    "west bengal": {"kharif": ["Rice", "Jute"], "rabi": ["Rice (Boro)", "Potato", "Mustard"]},
    "bihar": {"kharif": ["Rice", "Maize"], "rabi": ["Wheat", "Maize", "Lentil", "Potato"]},
    "odisha": {"kharif": ["Rice", "Groundnut"], "rabi": ["Rice", "Pulses", "Mustard"]},
    "chhattisgarh": {"kharif": ["Rice", "Maize", "Soybean"], "rabi": ["Wheat", "Gram", "Lathyrus"]},
    "assam": {"kharif": ["Rice (Sali)", "Jute"], "rabi": ["Rice (Boro)", "Mustard", "Potato"], "extra": ["Tea"]},
    "kerala": {"kharif": ["Rice", "Banana"], "rabi": ["Rice", "Vegetables"], "extra": ["Rubber", "Coconut", "Pepper", "Cardamom"]},
    "jharkhand": {"kharif": ["Rice", "Maize", "Pulses"], "rabi": ["Wheat", "Gram", "Mustard"]},
    "uttarakhand": {"kharif": ["Rice", "Ragi"], "rabi": ["Wheat", "Barley"]},
    "himachal pradesh": {"kharif": ["Maize", "Rice"], "rabi": ["Wheat", "Barley"], "extra": ["Apple"]},
}

_NATIONAL_DEFAULT = {
    "kharif": ["Rice", "Cotton", "Maize", "Soybean", "Groundnut"],
    "rabi": ["Wheat", "Mustard", "Gram", "Potato"],
}


def priors_for_state(state: str | None) -> dict[str, list[str]]:
    if not state:
        return dict(_NATIONAL_DEFAULT)
    return dict(_PRIORS.get(state.strip().lower(), _NATIONAL_DEFAULT))


def likely_crops(state: str | None) -> list[str]:
    data = priors_for_state(state)
    out: list[str] = []
    for group in ("kharif", "rabi", "extra"):
        for crop in data.get(group, []):
            if crop not in out:
                out.append(crop)
    return out
