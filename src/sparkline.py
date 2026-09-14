"""
sparkline.py
------------
Draws a tiny price chart as an SVG image.

We build the SVG in Python rather than using a JavaScript charting
library. That means no extra downloads, and the charts render on any
phone browser instantly.
"""


def make(closes, days=30, width=110, height=30):
    """
    Turn a list of closing prices into a small SVG line chart.
    Green if the period ended higher, red if it ended lower.
    """
    if not closes or len(closes) < 2:
        return ""

    points = closes[-days:]
    lowest = min(points)
    highest = max(points)
    span = highest - lowest

    # A flat line would divide by zero, so draw it down the middle.
    if span == 0:
        y_positions = [height / 2] * len(points)
    else:
        pad = 3
        usable = height - (pad * 2)
        # SVG y grows downward, so high prices need small y values
        y_positions = [
            pad + (usable * (1 - (p - lowest) / span)) for p in points
        ]

    step = width / (len(points) - 1)
    coords = " ".join(
        f"{i * step:.1f},{y:.1f}" for i, y in enumerate(y_positions)
    )

    rising = points[-1] >= points[0]
    color = "#16a34a" if rising else "#dc2626"
    fill = "#16a34a1a" if rising else "#dc26261a"

    # A filled area under the line, plus the line itself, plus a dot
    # marking the most recent price.
    area = f"0,{height} {coords} {width},{height}"

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="none" role="img">'
        f'<polygon points="{area}" fill="{fill}" />'
        f'<polyline points="{coords}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />'
        f'<circle cx="{width}" cy="{y_positions[-1]:.1f}" r="2" fill="{color}" />'
        f'</svg>'
    )
