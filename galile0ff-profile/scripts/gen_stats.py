#!/usr/bin/env python3
"""GitHub profil istatistiklerini çekip assets/stats.svg ve assets/langs.svg üretir.

Üçüncü parti görsel servislerine bağımlılık yok: SVG'ler repo içinde durur,
GitHub Actions ile periyodik güncellenir. Sadece standart kütüphane kullanır.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("GH_USER", "galile0ff")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")


def call(url, payload=None):
    headers = {"User-Agent": "profile-stats", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def collect():
    data = {"repos": "—", "stars": "—", "followers": "—", "commits": "—",
            "prs": "—", "issues": "—", "contrib": "—"}
    langs = {}

    profile = call(f"{API}/users/{USER}")
    data["followers"] = profile.get("followers", "—")

    repos, page = [], 1
    while True:
        chunk = call(f"{API}/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    data["repos"] = len(own)
    data["stars"] = sum(r["stargazers_count"] for r in own)

    for r in own[:60]:
        try:
            for lang, size in call(f"{API}/repos/{r['full_name']}/languages").items():
                langs[lang] = langs.get(lang, 0) + size
        except Exception:
            continue

    if TOKEN:
        try:
            q = """query($login:String!){user(login:$login){
              contributionsCollection{
                totalCommitContributions totalPullRequestContributions
                totalIssueContributions
                contributionCalendar{totalContributions}}}}"""
            res = call(f"{API}/graphql", {"query": q, "variables": {"login": USER}})
            c = res["data"]["user"]["contributionsCollection"]
            data["commits"] = c["totalCommitContributions"]
            data["prs"] = c["totalPullRequestContributions"]
            data["issues"] = c["totalIssueContributions"]
            data["contrib"] = c["contributionCalendar"]["totalContributions"]
        except Exception:
            pass
    return data, langs


CSS = """<style>
text{font-family:'JetBrains Mono','Fira Code',Consolas,'Courier New',monospace;font-size:13px;fill:#c9d1d9}
.g{fill:#00ff41}.d{fill:#8b949e}.b{font-weight:700}
</style>"""


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
{CSS}
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="#0d1117" stroke="#30363d"/>
<path d="M0.5 34 V10.5 a10 10 0 0 1 10 -10 H{w-10.5} a10 10 0 0 1 10 10 V34 z" fill="#161b22"/>
<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="38" cy="18" r="5" fill="#ffbd2e"/><circle cx="56" cy="18" r="5" fill="#27c93f"/>
<text x="{w/2}" y="22" text-anchor="middle" class="d" style="font-size:12px">{escape(title)}</text>
{body}
</svg>
"""


def stats_svg(d):
    rows = [
        ("repo", d["repos"]),
        ("star", d["stars"]),
        ("takipçi", d["followers"]),
        ("commit (12 ay)", d["commits"]),
        ("pull request", d["prs"]),
        ("issue", d["issues"]),
        ("toplam katkı", d["contrib"]),
    ]
    w, h = 400, 240
    body = [f'<text x="20" y="58"><tspan class="g">$</tspan> ./stats --user {escape(USER)}</text>']
    y = 84
    for k, v in rows:
        body.append(f'<text x="20" y="{y}"><tspan class="g">[+]</tspan> {escape(k)}</text>')
        body.append(f'<text x="{w-20}" y="{y}" text-anchor="end" class="g b">{escape(str(v))}</text>')
        y += 22
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body.append(f'<text x="20" y="{h-10}" class="d" style="font-size:10px"># güncellendi: {day}</text>')
    return frame(w, h, "telemetry.sh", "\n".join(body))


def langs_svg(langs):
    w, h = 400, 240
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:7]
    body = ['<text x="20" y="58"><tspan class="g">$</tspan> ./langs --top</text>']
    y = 82
    shades = ["1", ".88", ".76", ".64", ".52", ".42", ".34"]
    if not top:
        body.append(f'<text x="20" y="{y}" class="d"># veri yok, workflow\'u çalıştır</text>')
    for i, (name, size) in enumerate(top):
        pct = size / total * 100
        bar = max(2, 190 * pct / 100 * (100 / (top[0][1] / total * 100)))
        bar = min(bar, 190)
        body.append(f'<text x="20" y="{y}">{escape(name)}</text>')
        body.append(f'<rect x="130" y="{y-10}" width="190" height="10" rx="2" fill="#161b22"/>')
        body.append(f'<rect x="130" y="{y-10}" width="{bar:.1f}" height="10" rx="2" fill="#00ff41" fill-opacity="{shades[i]}"/>')
        body.append(f'<text x="{w-20}" y="{y}" text-anchor="end" class="d">{pct:.1f}%</text>')
        y += 22
    return frame(w, h, "langs.sh", "\n".join(body))


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        data, langs = collect()
    except Exception as e:  # API erişilemezse kartlar yine de render olsun
        print("uyarı: veri çekilemedi ->", e)
        data = {"repos": "—", "stars": "—", "followers": "—", "commits": "—",
                "prs": "—", "issues": "—", "contrib": "—"}
        langs = {}
    with open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(data))
    with open(os.path.join(OUT, "langs.svg"), "w", encoding="utf-8") as f:
        f.write(langs_svg(langs))
    print("ok:", data, dict(sorted(langs.items(), key=lambda x: -x[1])[:5]))


if __name__ == "__main__":
    main()
