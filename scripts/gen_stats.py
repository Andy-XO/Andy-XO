#!/usr/bin/env python3
"""
Generate a premium, cyan/electric-blue GitHub stats card as a self-contained SVG.

- Pulls PUBLIC data from the GitHub REST API (followers, repos, stars, forks,
  aggregated top languages).
- Writes a handcrafted dark-theme SVG to the output path.
- Served straight from the repo, so it can NEVER be rate-limited like the
  public github-readme-stats / trophy instances.

Usage:
    python scripts/gen_stats.py <github_user> <output_svg_path>

Auth:
    Reads GITHUB_TOKEN from the environment if present (raises the API rate
    limit and is provided automatically inside GitHub Actions). Works without a
    token too, just with a lower rate limit.
"""
import json
import os
import sys
import urllib.request
import urllib.error

API = "https://api.github.com"

# Theme — must match the profile (cyan / electric blue on space-black).
BG = "#05070D"
GRID = "#12243B"
CARD = "#0A0F1C"
CARD_STROKE = "#16324B"
CYAN = "#00D9FF"
BLUE = "#33A1FF"
INDIGO = "#6E7BFF"
TEXT = "#F4FAFF"
MUTED = "#9FB4C7"
SUBTLE = "#5FC9F8"

# Language bar palette — theme-aligned shades (cyan → indigo → soft accents).
LANG_PALETTE = ["#00D9FF", "#33A1FF", "#6E7BFF", "#3FCF8E", "#FFD21E", "#FF6F61", "#A78BFA"]


def api_get(path, token):
    url = path if path.startswith("http") else API + path
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "andy-xo-stats-card",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def collect(user, token):
    """Return a dict of headline stats + aggregated language byte counts."""
    u = api_get(f"/users/{user}", token)
    stats = {
        "followers": u.get("followers", 0),
        "following": u.get("following", 0),
        "public_repos": u.get("public_repos", 0),
        "stars": 0,
        "forks": 0,
    }

    # Page through owned public repos.
    repos = []
    page = 1
    while page <= 5:  # cap at 500 repos
        chunk = api_get(f"/users/{user}/repos?per_page=100&type=owner&sort=updated&page={page}", token)
        if not chunk:
            break
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1

    langs = {}
    for r in repos:
        if r.get("fork"):
            continue
        stats["stars"] += r.get("stargazers_count", 0)
        stats["forks"] += r.get("forks_count", 0)
        # Aggregate language bytes (best-effort; skip on error).
        try:
            for lang, b in api_get(r["languages_url"], token).items():
                langs[lang] = langs.get(lang, 0) + b
        except Exception:
            pass

    return stats, langs


def fmt(n):
    if n >= 1000:
        return f"{n/1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def top_languages(langs, k=6):
    items = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:k]
    total = sum(v for _, v in items) or 1
    return [(name, v, v / total) for name, v in items]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(user, stats, langs):
    W, H = 900, 350
    tiles = [
        ("FOLLOWERS", fmt(stats["followers"])),
        ("PUBLIC REPOS", fmt(stats["public_repos"])),
        ("TOTAL STARS", fmt(stats["stars"])),
        ("TOTAL FORKS", fmt(stats["forks"])),
    ]

    # --- header + defs ---
    parts = [f'''<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub statistics for {esc(user)}">
  <defs>
    <linearGradient id="acc" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{CYAN}"/><stop offset="50%" stop-color="{BLUE}"/><stop offset="100%" stop-color="{INDIGO}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="0%" r="80%">
      <stop offset="0%" stop-color="{CYAN}" stop-opacity="0.16"/><stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">
      <path d="M36 0 L0 0 0 36" fill="none" stroke="{GRID}" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="{W}" height="{H}" rx="16" fill="{BG}"/>
  <rect width="{W}" height="{H}" rx="16" fill="url(#grid)" opacity="0.5"/>
  <rect width="{W}" height="160" fill="url(#glow)"/>
  <g stroke="{CYAN}" stroke-width="2" opacity="0.6" fill="none">
    <path d="M18 18 H50 M18 18 V50"/><path d="M{W-18} 18 H{W-50} M{W-18} 18 V50"/>
    <path d="M18 {H-18} H50 M18 {H-18} V{H-50}"/><path d="M{W-18} {H-18} H{W-50} M{W-18} {H-18} V{H-50}"/>
  </g>

  <text x="40" y="52" font-family="'Segoe UI',Arial,sans-serif" font-size="13" letter-spacing="5" fill="{SUBTLE}" font-weight="600">GITHUB ANALYTICS</text>
  <text x="40" y="80" font-family="'Segoe UI',Arial,sans-serif" font-size="24" font-weight="800" fill="{TEXT}">@{esc(user)}</text>
  <rect x="40" y="92" width="120" height="3" rx="1.5" fill="url(#acc)"/>
''']

    # --- stat tiles ---
    tile_w, tile_h, gap, x0, y0 = 196, 96, 18, 40, 116
    for i, (label, value) in enumerate(tiles):
        x = x0 + i * (tile_w + gap)
        parts.append(f'''  <g>
    <rect x="{x}" y="{y0}" width="{tile_w}" height="{tile_h}" rx="12" fill="{CARD}" stroke="{CARD_STROKE}" stroke-width="1"/>
    <rect x="{x}" y="{y0}" width="4" height="{tile_h}" rx="2" fill="url(#acc)"/>
    <text x="{x+22}" y="{y0+46}" font-family="'Segoe UI',Arial,sans-serif" font-size="34" font-weight="800" fill="{TEXT}">{esc(value)}</text>
    <text x="{x+22}" y="{y0+72}" font-family="'Segoe UI',Arial,sans-serif" font-size="11" letter-spacing="2" fill="{MUTED}" font-weight="600">{label}</text>
  </g>
''')

    # --- languages bar ---
    bar_y = 250
    bar_x = 40
    bar_w = W - 80
    parts.append(f'  <text x="{bar_x}" y="{bar_y-14}" font-family="\'Segoe UI\',Arial,sans-serif" font-size="12" letter-spacing="3" fill="{SUBTLE}" font-weight="600">MOST USED LANGUAGES</text>\n')

    tops = top_languages(langs)
    if tops:
        # stacked rounded bar
        parts.append(f'  <clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="16" rx="8"/></clipPath>\n')
        parts.append(f'  <g clip-path="url(#barclip)">\n')
        cx = bar_x
        for i, (name, _b, frac) in enumerate(tops):
            seg = max(frac * bar_w, 2)
            color = LANG_PALETTE[i % len(LANG_PALETTE)]
            parts.append(f'    <rect x="{cx:.1f}" y="{bar_y}" width="{seg:.1f}" height="16" fill="{color}"/>\n')
            cx += seg
        parts.append(f'    <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="16" fill="none"/>\n')
        parts.append('  </g>\n')
        # legend
        ly = bar_y + 46
        lx = bar_x
        for i, (name, _b, frac) in enumerate(tops):
            color = LANG_PALETTE[i % len(LANG_PALETTE)]
            label = f"{esc(name)} {frac*100:.1f}%"
            parts.append(f'  <circle cx="{lx+6}" cy="{ly-4}" r="6" fill="{color}"/>\n')
            parts.append(f'  <text x="{lx+20}" y="{ly}" font-family="\'Segoe UI\',Arial,sans-serif" font-size="13" fill="{MUTED}">{label}</text>\n')
            lx += 28 + (len(label) * 7.6)
    else:
        parts.append(f'  <text x="{bar_x}" y="{bar_y+12}" font-family="\'Segoe UI\',Arial,sans-serif" font-size="13" fill="{MUTED}">No public language data yet.</text>\n')

    # animated pulse accent (keeps it feeling "live")
    parts.append(f'''  <line x1="40" y1="{H-26}" x2="{W-40}" y2="{H-26}" stroke="{GRID}" stroke-width="1"/>
  <circle cx="40" cy="{H-26}" r="3.5" fill="{CYAN}">
    <animate attributeName="cx" values="40;{W-40};40" dur="6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.2;1;0.2" dur="6s" repeatCount="indefinite"/>
  </circle>
''')

    parts.append("</svg>\n")
    return "".join(parts)


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else "Andy-XO"
    out = sys.argv[2] if len(sys.argv) > 2 else "assets/stats.svg"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    stats, langs = collect(user, token)
    svg = build_svg(user, stats, langs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {out}")
    print("stats:", json.dumps(stats))
    print("languages:", ", ".join(f"{name}={frac*100:.1f}%" for name, _b, frac in top_languages(langs)) if langs else "none")


if __name__ == "__main__":
    main()
