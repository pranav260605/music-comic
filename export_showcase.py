import asyncio
import base64
import io
import json
import os
import re
import shutil
from pathlib import Path
import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent

# Load backend/.env
for env_path in [ROOT / "backend" / ".env", ROOT / ".env"]:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

AUDIO_DIR = ROOT / "audio_clips"
DOCS_DIR = ROOT / "docs"
SHOWS_DIR = DOCS_DIR / "shows"

# Exact style palette & names matching the original Song-to-Comic Studio
ALL_STYLES = [
    {"id": "shonen", "name": "Shonen Action", "desc": "Speed lines, bold yellow/red energy", "color": "#ffd60a"},
    {"id": "cinematic_anime", "name": "Cinematic Anime", "desc": "Golden-hour film light and depth", "color": "#f6a04d"},
    {"id": "dark_fantasy", "name": "Gothic Noir", "desc": "Moody shadows & dramatic ink", "color": "#a78bd8"},
    {"id": "classic_manga", "name": "Classic Manga", "desc": "Ink, screentone, hatching", "color": "#ffffff"},
    {"id": "modern_anime", "name": "Modern Anime", "desc": "Clean cel shading", "color": "#9bd7ff"},
    {"id": "shojo", "name": "Shojo Romance", "desc": "Delicate, sparkling", "color": "#ffc0d9"},
    {"id": "watercolor", "name": "Watercolor", "desc": "Soft washes", "color": "#bfe6d4"},
    {"id": "retro_anime", "name": "Retro Anime", "desc": "90s grain and colour", "color": "#f2c48d"},
    {"id": "soft_romantic", "name": "Soft Romantic", "desc": "Pastel glow", "color": "#ffd9d0"},
    {"id": "fantasy_illustration", "name": "Fantasy Illustration", "desc": "Ornate, detailed", "color": "#d7c08a"},
]

STYLE_PROMPTS = {
    "shonen": (
        "High-energy Shonen action comic art, bold thick black ink outlines, vibrant comic yellow (#FFD60A) and "
        "crimson red (#D72631) highlights, dynamic speed lines, expressive anime faces, cel-shaded drama, NO text bubbles"
    ),
    "cinematic_anime": (
        "Makoto Shinkai inspired golden-hour cinematic anime film still, blazing sunset sky, dramatic rim lighting, "
        "anamorphic lens flare, richly painted background and expressive characters, NO text"
    ),
    "dark_fantasy": (
        "Gothic noir graphic novel illustration, moody chiaroscuro shadows, rain-slicked twilight stone architecture, "
        "crimson and amber streetlamp glow, rich comic-book ink wash, NO text"
    ),
}

SONGS = [
    {
        "id": "rowdy_baby",
        "title": "Rowdy Baby",
        "artist": "Dhanush & Dhee (Maari 2)",
        "language": "Tamil / English",
        "genre": "Tamil Festive Pop",
        "bpm": 132,
        "audio_file": "Rowdy Baby.mp3",
        "default_style": "shonen",
        "enabled_styles": ["shonen", "cinematic_anime", "dark_fantasy"],
        "lyrics_full": (
            "Hey en goli sodaave, en kari kozhambae!\n"
            "Un kutty puppy naan, take me, take me!\n"
            "Hey rowdy baby... unnale mood aachu!\n"
            "One plus one two mama, you plus me free mama!"
        ),
        "notes": "Playful Chennai street romance & energetic dance celebration between a charismatic local hero and his bold partner.",
        "scene_concept": "Charismatic young South Indian hero in casual street-style sunglasses and shirt dancing playfully with a spirited young woman in vibrant festive attire on a colorful Chennai street.",
        "panels_timing": [
            {"start": 0.0, "end": 4.5, "caption": "Hey en goli sodaave, en kari kozhambae!", "sfx": "DANCE!"},
            {"start": 4.5, "end": 9.0, "caption": "Un kutty puppy naan, take me, take me!", "sfx": "WHOOSH!"},
            {"start": 9.0, "end": 14.0, "caption": "Hey rowdy baby... unnale mood aachu!", "sfx": "BOOM!"},
            {"start": 14.0, "end": 22.0, "caption": "One plus one two mama, you plus me free mama!", "sfx": "PARTY!"},
        ],
    },
    {
        "id": "derniere_danse",
        "title": "Dernière Danse",
        "artist": "Indila",
        "language": "French / Global",
        "genre": "Dramatic Chanson Pop",
        "bpm": 115,
        "audio_file": "Danse Danse.mp3",
        "default_style": "dark_fantasy",
        "enabled_styles": ["dark_fantasy", "cinematic_anime", "shonen"],
        "lyrics_full": (
            "Oh ma douce souffrance... pourquoi s'acharner ?\n"
            "Je ne suis qu'un être sans importance...\n"
            "Je remue le ciel, le jour, la nuit...\n"
            "Je danse avec le vent, la pluie..."
        ),
        "notes": "Poetic struggle against sorrow in twilight Paris—turning pain and solitude into a defiant dance with the wind and rain.",
        "scene_concept": "Theatrical street performer in a tailored crimson velvet coat dancing gracefully down rain-slicked twilight Parisian stone steps beside glowing vintage streetlamps.",
        "panels_timing": [
            {"start": 0.0, "end": 5.0, "caption": "Oh ma douce souffrance... pourquoi s'acharner ?", "sfx": "DRIP..."},
            {"start": 5.0, "end": 10.0, "caption": "Je ne suis qu'un être sans importance...", "sfx": "WIND!"},
            {"start": 10.0, "end": 15.0, "caption": "Je remue le ciel, le jour, la nuit...", "sfx": "SWIRL!"},
            {"start": 15.0, "end": 22.0, "caption": "Je danse avec le vent, la pluie...", "sfx": "CLIMAX!"},
        ],
    },
    {
        "id": "believer",
        "title": "Believer",
        "artist": "Imagine Dragons",
        "language": "English",
        "genre": "Arena Pop-Rock",
        "bpm": 125,
        "audio_file": "Believer.mp3",
        "default_style": "cinematic_anime",
        "enabled_styles": ["cinematic_anime", "shonen", "dark_fantasy"],
        "lyrics_full": (
            "First things first, I'ma say all the words inside my head...\n"
            "I'm fired up and tired of the way that things have been...\n"
            "PAIN! You made me a, you made me a BELIEVER!\n"
            "Let the bullets fly, let them rain..."
        ),
        "notes": "Rising above self-doubt and hardship on a sunset rooftop, transforming every setback into unbreakable creative fire.",
        "scene_concept": "Determined young dreamer wearing a knit beanie standing on a city rooftop at sunset, silhouetted against a blazing orange-crimson sky as golden embers rise.",
        "panels_timing": [
            {"start": 0.0, "end": 5.0, "caption": "First things first, I'ma say all the words inside my head...", "sfx": "PULSE!"},
            {"start": 5.0, "end": 10.0, "caption": "I'm fired up and tired of the way that things have been...", "sfx": "IGNITE!"},
            {"start": 10.0, "end": 15.0, "caption": "PAIN! You made me a, you made me a BELIEVER!", "sfx": "CRACK!"},
            {"start": 15.0, "end": 22.0, "caption": "Let the bullets fly, let them rain...", "sfx": "RISE!"},
        ],
    },
    {
        "id": "sing_about_me",
        "title": "Sing About Me",
        "artist": "Kendrick Lamar",
        "language": "English",
        "genre": "Conscious Hip-Hop",
        "bpm": 96,
        "audio_file": "Sing about me.mp3",
        "default_style": "dark_fantasy",
        "enabled_styles": ["dark_fantasy", "shonen", "cinematic_anime"],
        "lyrics_full": (
            "When the lights shut off and it's my turn to settle down...\n"
            "My main concern: promise that you will sing about me...\n"
            "Walking down this midnight avenue, streetlamps glowing...\n"
            "Promise that you will sing about me..."
        ),
        "notes": "Midnight reflection along quiet city avenues—honoring memory, legacy, and stories that outlive the night.",
        "scene_concept": "Young poet in an oversized hoodie walking thoughtfully along a quiet midnight avenue beside a classic parked car under warm amber streetlamps.",
        "panels_timing": [
            {"start": 0.0, "end": 5.5, "caption": "When the lights shut off and it's my turn to settle down...", "sfx": "FADE..."},
            {"start": 5.5, "end": 11.0, "caption": "My main concern: promise that you will sing about me...", "sfx": "ECHO!"},
            {"start": 11.0, "end": 16.5, "caption": "Walking down this midnight avenue, streetlamps glowing...", "sfx": "STEP..."},
            {"start": 16.5, "end": 22.0, "caption": "Promise that you will sing about me...", "sfx": "LEGACY!"},
        ],
    },
]

DIRECTOR_SYSTEM = """You are a senior comic-book art director and music-video storyboarder.
Given a song's lyrics, concept, and visual art style, return ONLY valid raw JSON (no markdown fences) with:
{
  "story_summary": "A vivid 2-3 sentence comic-book synopsis of the song's emotional arc.",
  "characters": [
    {"name": "Character Name", "role": "Protagonist / Partner", "visual_design": "Brief outfit & appearance description"}
  ],
  "story_beats": [
    {"beat": 1, "tag": "explicit", "title": "Opening Hook", "description": "What happens in Panel 1"},
    {"beat": 2, "tag": "inferred", "title": "Rising Rhythm", "description": "What happens in Panel 2"},
    {"beat": 3, "tag": "creative_interpretation", "title": "The Chorus Peak", "description": "What happens in Panel 3"},
    {"beat": 4, "tag": "creative_interpretation", "title": "Final Freeze-Frame", "description": "What happens in Panel 4"}
  ],
  "panels": [
    {
      "panel_num": 1,
      "camera_motion": "zoom_in",
      "image_prompt": "Detailed widescreen comic panel illustration keeping exact same character appearance and outfits, rich background, dynamic angle, NO text, NO speech bubbles."
    },
    {
      "panel_num": 2,
      "camera_motion": "pan_right",
      "image_prompt": "Detailed widescreen comic panel illustration continuing the action with exact same characters, dynamic angle, NO text, NO speech bubbles."
    },
    {
      "panel_num": 3,
      "camera_motion": "hero_punch",
      "image_prompt": "Dramatic climax widescreen comic panel illustration with exact same characters, bold lighting, NO text, NO speech bubbles."
    },
    {
      "panel_num": 4,
      "camera_motion": "pan_left",
      "image_prompt": "Memorable closing widescreen comic panel illustration with exact same characters, cinematic framing, NO text, NO speech bubbles."
    }
  ]
}"""


def _headers(api_key: str) -> dict:
    token = api_key if ":" in api_key else f"{api_key}:music-to-comic"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def call_pro_director(song: dict, style_id: str) -> dict:
    api_key = os.environ["LLM_API_KEY"].strip()
    base = os.getenv("LLM_TEXT_BASE_URL", "https://llmfoundry.straive.com/gemini/v1beta/openai").rstrip("/")
    # Use gemini-2.5-pro first for superior storyboard & character consistency
    models = ["gemini-2.5-pro", "gemini-2.5-flash"]
    style_desc = STYLE_PROMPTS[style_id]
    user = (
        f"Song: {song['title']} by {song['artist']}\n"
        f"Lyrics:\n{song['lyrics_full']}\n"
        f"Notes: {song['notes']}\n"
        f"Core Concept: {song['scene_concept']}\n"
        f"Target Art Style: {style_desc}\n"
        f"Ensure ALL 4 panel image_prompts explicitly include the art style and keep the exact same character clothing/features across all 4 panels. Return ONLY JSON."
    )

    for model in models:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=240, verify=False, trust_env=False) as client:
                    r = await client.post(
                        f"{base}/chat/completions",
                        headers=_headers(api_key),
                        json={
                            "model": model,
                            "temperature": 0.4,
                            "messages": [
                                {"role": "system", "content": DIRECTOR_SYSTEM},
                                {"role": "user", "content": user},
                            ],
                        },
                    )
                    if r.status_code == 400 and "does not exist" in r.text:
                        break
                    r.raise_for_status()
                    txt = r.json()["choices"][0]["message"]["content"]
                    cleaned = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
                    s, e = cleaned.find("{"), cleaned.rfind("}")
                    return json.loads(cleaned[s : e + 1])
            except (httpx.ReadTimeout, httpx.ConnectTimeout):
                if attempt == 2:
                    raise
                print(f"    [RETRY] Timeout on {model}, retrying ({attempt + 2}/3)...")
                await asyncio.sleep(3)
    raise RuntimeError("No Gemini director model responded.")


async def generate_hd_panel(prompt: str) -> Image.Image:
    api_key = os.environ["LLM_API_KEY"].strip()
    base = os.getenv("LLM_IMAGE_BASE_URL", "https://llmfoundry.straive.com/openai/v1").rstrip("/")
    # High-tier image models on LLM Foundry (ordered by quality)
    candidates = ["gpt-image-1.5", "dall-e-3", "gpt-image-1-mini"]

    last_err = ""
    for attempt in range(2):
        async with httpx.AsyncClient(timeout=300, verify=False, trust_env=False) as client:
            for model in candidates:
                is_gpt_img = model.startswith("gpt-image")
                req_size = "1536x1024" if is_gpt_img else "1792x1024"
                payload = {"model": model, "prompt": prompt, "n": 1, "size": req_size}

                if is_gpt_img:
                    payload["quality"] = "high"
                elif model == "dall-e-3":
                    payload["quality"] = "hd"

                try:
                    r = await client.post(f"{base}/images/generations", headers=_headers(api_key), json=payload)
                except (httpx.ReadTimeout, httpx.ConnectTimeout):
                    last_err = f"Timeout on {model}"
                    continue

                if r.status_code == 400 and "does not exist" in r.text:
                    last_err = r.text[:200]
                    continue
                if r.status_code == 400 and "moderation_block" in r.text:
                    payload["prompt"] = "Vibrant widescreen comic book illustration of an energetic musical performance on a colorful city street, dynamic lighting, bold ink lines, NO text."
                    r = await client.post(f"{base}/images/generations", headers=_headers(api_key), json=payload)

                if r.status_code >= 400:
                    last_err = f"{r.status_code} ({model}): {r.text[:200]}"
                    continue

                item = r.json()["data"][0]
                raw = base64.b64decode(item["b64_json"]) if item.get("b64_json") else (await client.get(item["url"])).content
                print(f"      -> Rendered HD panel with {model}")
                return Image.open(io.BytesIO(raw)).convert("RGB")

    raise RuntimeError(f"Image generation failed across models. Last error: {last_err}")


async def build_variant(song: dict, style_id: str, force: bool = False):
    vdir = SHOWS_DIR / song["id"] / style_id
    scene_file = vdir / "scene.json"
    if scene_file.exists() and not force:
        print(f"  [SKIP] {song['id']} / {style_id} already upgraded.")
        return

    vdir.mkdir(parents=True, exist_ok=True)
    # Remove any old cutout files from v1
    for old in ["bg.webp", "bg.avif", "pose_a.webp", "pose_b.webp"]:
        p = vdir / old
        if p.exists():
            p.unlink()

    print(f"  [GEN ] {song['title']} -> {style_id} (Pro Storyboard + 4 HD Panels)...")
    plan = await call_pro_director(song, style_id)

    panels_out = []
    timings = song["panels_timing"]
    for idx, p_spec in enumerate(plan["panels"][:4]):
        img = await generate_hd_panel(p_spec["image_prompt"])
        fname = f"panel_{idx + 1}.webp"
        img.save(vdir / fname, format="WEBP", quality=88, method=4)
        t_info = timings[idx] if idx < len(timings) else timings[-1]
        panels_out.append({
            "panel_num": idx + 1,
            "file": fname,
            "start": t_info["start"],
            "end": t_info["end"],
            "caption": t_info["caption"],
            "sfx": t_info["sfx"],
            "camera_motion": p_spec.get("camera_motion", "zoom_in"),
        })

    scene_data = {
        "song_id": song["id"],
        "style_id": style_id,
        "bpm": song["bpm"],
        "story_summary": plan.get("story_summary", song["notes"]),
        "characters": plan.get("characters", []),
        "story_beats": plan.get("story_beats", []),
        "panels": panels_out,
    }
    scene_file.write_text(json.dumps(scene_data, indent=2), encoding="utf-8")
    print(f"  [DONE] Saved 4 HD panels in {vdir}")


async def main():
    SHOWS_DIR.mkdir(parents=True, exist_ok=True)
    catalog_songs = []

    for song in SONGS:
        sdir = SHOWS_DIR / song["id"]
        sdir.mkdir(parents=True, exist_ok=True)
        src_audio = AUDIO_DIR / song["audio_file"]
        dst_audio = sdir / "audio.mp3"
        if src_audio.exists():
            shutil.copy2(src_audio, dst_audio)

        # force=True so it upgrades all 12 variants to the new 4-panel HD comic architecture
        for style_id in song["enabled_styles"]:
            await build_variant(song, style_id, force=True)

        catalog_songs.append({
            "id": song["id"],
            "title": song["title"],
            "artist": song["artist"],
            "language": song["language"],
            "genre": song["genre"],
            "bpm": song["bpm"],
            "lyrics_full": song["lyrics_full"],
            "notes": song["notes"],
            "default_style": song["default_style"],
            "enabled_styles": song["enabled_styles"],
            "thumbnail": f"shows/{song['id']}/{song['default_style']}/panel_1.webp",
            "audio": f"shows/{song['id']}/audio.mp3",
        })

    catalog = {"styles": ALL_STYLES, "songs": catalog_songs}
    (DOCS_DIR / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print("\nAll 12 HD 4-panel comic showcases & docs/catalog.json are ready!")


if __name__ == "__main__":
    asyncio.run(main())