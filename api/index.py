"""
DeadToons Flask Site — Vercel
Backend: Cloudflare Worker (unlock + image proxy)
"""
import os
import re
import json
from urllib.parse import quote
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# ─── CONFIG ──────────────────────────────────────────────
API    = "https://api.deadbase.host/api/v1/public"
SITE   = "https://deadtoons.sbs"

# 👇👇👇 APNA WORKER URL YAHAN DAAL 👇👇👇
WORKER = os.environ.get("WORKER_URL", "https://dt-worker.aakigopro1470.workers.dev")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/137.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA}


# ─── CSS ─────────────────────────────────────────────────
CSS = """
:root{--bg:#0b0b0e;--card:#14141a;--border:#23232c;--fg:#eaeaf0;
--muted:#8a8a96;--accent:#ff6b35}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:ui-sans-serif,system-ui,sans-serif;min-height:100vh}
header{display:flex;align-items:center;gap:1rem;padding:.9rem 1.5rem;
border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;
background:rgba(11,11,14,.85);backdrop-filter:blur(8px)}
.brand{font-weight:800;font-size:1.1rem;color:var(--fg);text-decoration:none}
.brand span{color:var(--accent)}
.searchbar{flex:1;max-width:560px}
.searchbar input{width:100%;padding:.6rem 1rem;background:var(--card);
border:1px solid var(--border);border-radius:8px;color:var(--fg);font-size:.9rem;outline:none}
.searchbar input:focus{border-color:var(--accent)}
main{max-width:1200px;margin:0 auto;padding:1.5rem}
h1{font-size:1.1rem;color:var(--muted);margin:0 0 1rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;
overflow:hidden;text-decoration:none;color:inherit;display:flex;flex-direction:column;
transition:transform .15s,border-color .15s}
.card:hover{transform:translateY(-3px);border-color:var(--accent)}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#1a1a20}
.card .meta{padding:.6rem .7rem .8rem}
.card h3{font-size:.82rem;font-weight:600;line-height:1.3;margin:0 0 .35rem;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .row{display:flex;justify-content:space-between;font-size:.7rem;color:var(--muted)}
.badge{display:inline-block;padding:.1rem .45rem;border-radius:4px;font-size:.65rem;
background:var(--accent);color:#000;font-weight:700;text-transform:uppercase}
.badge.ongoing{background:#22c55e}
.badge.completed{background:#64748b;color:#fff}
.pager{display:flex;justify-content:center;gap:.5rem;margin:2rem 0}
.pager a,.pager span{padding:.5rem .9rem;border:1px solid var(--border);
border-radius:6px;color:var(--fg);text-decoration:none;font-size:.85rem}
.pager a:hover{border-color:var(--accent)}
.pager .active{background:var(--accent);color:#000;border-color:var(--accent);font-weight:700}
.detail{display:grid;grid-template-columns:300px 1fr;gap:1.5rem}
@media(max-width:720px){.detail{grid-template-columns:1fr}}
.detail img.hero{width:100%;border-radius:10px;border:1px solid var(--border)}
.detail h1{color:var(--fg);font-size:1.4rem;margin:0 0 .5rem}
.detail .desc{color:var(--muted);font-size:.9rem;line-height:1.6}
.ep-row{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0}
.ep-btn{padding:.5rem .8rem;background:var(--card);border:1px solid var(--border);
border-radius:6px;color:var(--fg);cursor:pointer;font-size:.82rem}
.ep-btn:hover{border-color:var(--accent)}
.ep-btn.active{border-color:var(--accent);background:#1e1e26}
.q-block{border:1px solid var(--border);border-radius:8px;padding:.8rem;margin-bottom:.6rem}
.q-head{display:flex;justify-content:space-between;margin-bottom:.5rem}
.srv-btn{padding:.5rem .9rem;background:var(--card);border:1px solid var(--border);
border-radius:6px;color:var(--fg);cursor:pointer;font-size:.82rem;margin:.2rem}
.srv-btn:hover{border-color:var(--accent)}
.srv-btn:disabled{opacity:.4;cursor:wait}
.result{margin-top:1rem;padding:1rem;border:1px solid var(--accent);
border-radius:8px;background:#1a1a20}
.result a{color:var(--accent);word-break:break-all}
.err{color:var(--accent);font-size:.85rem}
footer{text-align:center;padding:2rem 1rem;color:var(--muted);
font-size:.75rem;border-top:1px solid var(--border);margin-top:3rem}
"""


# ─── HTML SHELL ──────────────────────────────────────────
def shell(title, body, extra_js=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — DeadToons</title>
<style>{CSS}</style>
</head><body>
<header>
  <a href="/" class="brand">DeadToons<span>.web</span></a>
  <form action="/search" class="searchbar">
    <input type="search" name="q" placeholder="Search anime, movies, packs..."
           value="{request.args.get('q','')}" autocomplete="off">
  </form>
</header>
<main>{body}</main>
<footer>Personal use. Data from public DeadToons API.</footer>
<script>
const WORKER = "{WORKER}";
{extra_js}
</script>
</body></html>"""


# ─── HELPERS ─────────────────────────────────────────────
def img_url(raw):
    if not raw:
        return ""
    return f"{WORKER}/img?u={quote(raw, safe='')}"


def fetch_posts(page=1, limit=24):
    r = requests.get(f"{API}/posts", params={"page": page, "limit": limit},
                     headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def card_html(p):
    img = img_url(p.get("backdrop_img", {}).get("mid") or
                  p.get("backdrop_img", {}).get("low"))
    return f"""
    <a class="card" href="/anime/{p['slug']}">
      <img src="{img}" loading="lazy" alt="">
      <div class="meta">
        <h3>{p['title']}</h3>
        <div class="row">
          <span class="badge {p.get('status','')}">{p.get('status','')}</span>
          <span>★ {p.get('rating','0')}</span>
        </div>
      </div>
    </a>"""


# ─── ROUTES ──────────────────────────────────────────────
@app.route("/")
def home():
    try:
        page_num = max(1, int(request.args.get("page", 1)))
        data = fetch_posts(page_num, 24)
    except Exception as e:
        return shell("Error", f'<p class="err">Failed to load: {e}</p>')

    cards = "".join(card_html(p) for p in data.get("data", []))
    total = data.get("count", 0)
    total_pages = (total + 23) // 24
    prev_link = f'<a href="/?page={page_num-1}">← Prev</a>' if page_num > 1 else ""
    next_link = f'<a href="/?page={page_num+1}">Next →</a>' if page_num < total_pages else ""

    body = f"""
    <h1>Latest — {total:,} titles</h1>
    <div class="grid">{cards}</div>
    <div class="pager">{prev_link}<span class="active">{page_num}</span>
    <span>of {total_pages}</span>{next_link}</div>
    """
    return shell("Home", body)


@app.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return shell("Search", '<h1>Type something to search</h1>')

    needle = q.lower()
    results = []
    for page_num in range(1, 9):
        try:
            data = fetch_posts(page_num, 24)
        except Exception:
            break
        for p in data.get("data", []):
            hay = (p.get("title", "") + " " + p.get("anime_name", "") + " " +
                   " ".join(g.get("name", "") for g in p.get("genres", []))).lower()
            if needle in hay:
                results.append(p)
        if page_num * 24 >= data.get("count", 0):
            break

    cards = "".join(card_html(p) for p in results)
    body = f'<h1>Search: "{q}" — {len(results)} results</h1><div class="grid">{cards}</div>'
    return shell(f"Search {q}", body)


@app.route("/anime/<slug>")
def anime_detail(slug):
    try:
        r = requests.get(f"{SITE}/posts/{slug}", headers=HEADERS, timeout=15)
        html = r.text
    except Exception as e:
        return shell("Error", f'<p class="err">Failed to load post: {e}</p>')

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else slug

    og = soup.find("meta", property="og:image")
    poster = og["content"] if og else ""
    poster_proxied = img_url(poster) if poster else ""

    desc_meta = soup.find("meta", attrs={"name": "description"})
    desc = desc_meta["content"] if desc_meta else ""

    m = re.search(r'"anime_slug"\s*:\s*"([^"]+)"', html)
    anime_slug = m.group(1) if m else slug

    sm = re.search(r"season\s*(\d+)", title, re.I)
    season = int(sm.group(1)) if sm else 1

    eps = set()
    for a in soup.find_all("a", href=True):
        mm = re.search(r"/episode/[^/]+/(\d+)x(\d+)", a["href"])
        if mm:
            eps.add(int(mm.group(2)))
    episodes = sorted(eps) if eps else [1]

    ep_buttons = "".join(
        f'<button class="ep-btn" data-ep="{e}">Ep {e}</button>'
        for e in episodes[:300]
    )

    extra_js = f"""
const ANIME_SLUG = {json.dumps(anime_slug)};
const SEASON     = {season};

document.querySelectorAll('.ep-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadEpisode(parseInt(btn.dataset.ep));
  }});
}});

async function loadEpisode(ep) {{
  const box = document.getElementById('links');
  box.innerHTML = '<p style="color:#8a8a96">Loading links...</p>';
  try {{
    const r = await fetch(`/api/episode?slug=${{ANIME_SLUG}}&season=${{SEASON}}&episode=${{ep}}`);
    const data = await r.json();
    if (!data.links || !data.links.length) {{
      box.innerHTML = '<p class="err">No links for this episode.</p>';
      return;
    }}
    box.innerHTML = '';
    data.links.forEach(q => {{
      const block = document.createElement('div');
      block.className = 'q-block';
      let srvHTML = '';
      (q.servers || []).forEach(s => {{
        if ((s.name || '').toLowerCase() === 'telegram') return;
        srvHTML += `<button class="srv-btn" onclick="resolve({{${{s.link_server_id}}}}, this)">${{s.name}}</button>`;
      }});
      block.innerHTML = `<div class="q-head"><strong>${{q.quality || 'Unknown'}}</strong>
        <span style="color:#8a8a96;font-size:.8rem">${{q.size || ''}}</span></div>${{srvHTML}}`;
      box.appendChild(block);
    }});
  }} catch (e) {{
    box.innerHTML = '<p class="err">Error: ' + e.message + '</p>';
  }}
}}

async function resolve(lsid, btn) {{
  const out = document.getElementById('result');
  out.innerHTML = '<p style="color:#8a8a96">Unlocking ' + lsid + '...</p>';
  btn.disabled = true;
  try {{
    const r = await fetch(`${{WORKER}}/unlock/${{lsid}}`, {{ method: 'POST' }});
    const j = await r.json();
    if (j.ok && j.url) {{
      out.className = 'result';
      out.innerHTML = '<strong style="color:#ff6b35">Ready</strong><br><a href="' +
        j.url + '" target="_blank" rel="noopener">' + j.url + '</a>';
    }} else {{
      out.className = 'err';
      out.innerHTML = 'Failed: ' + (j.error || 'unknown');
    }}
  }} catch (e) {{
    out.className = 'err';
    out.innerHTML = 'Error: ' + e.message;
  }} finally {{
    btn.disabled = false;
  }}
}}

window.addEventListener('DOMContentLoaded', () => {{
  const first = document.querySelector('.ep-btn');
  if (first) first.click();
}});
"""

    body = f"""
    <div class="detail">
      <div><img class="hero" src="{poster_proxied}" alt=""></div>
      <div>
        <h1>{title}</h1>
        <p class="desc">{desc}</p>
        <h3 style="font-size:.95rem;margin-top:1rem">Episodes — Season {season}</h3>
        <div class="ep-row">{ep_buttons}</div>
        <div id="links"></div>
        <div id="result"></div>
      </div>
    </div>
    """
    return shell(title, body, extra_js)


@app.route("/api/episode")
def api_episode():
    slug    = request.args.get("slug", "")
    season  = request.args.get("season", "1")
    episode = request.args.get("episode", "1")
    if not slug:
        return jsonify({"links": []})
    try:
        r = requests.get(f"{API}/anime/{slug}/season/{season}/episode/{episode}",
                         headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return jsonify({"links": []})
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"links": [], "error": str(e)})


@app.route("/health")
def health():
    return jsonify({"ok": True, "worker": WORKER})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
