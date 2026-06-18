---
name: music
description: "Music creation, generation, and analysis: songwriting craft, AI music generation (HeartMuLa), and audio visualization (spectrograms). Use when writing songs, generating music from text, or analyzing audio."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [music, songwriting, audio, generation, ai, spectrogram, visualization, lyrics, suno]
    related_skills: [audiocraft-audio-generation]
---

# Music: Creation, Generation & Analysis

Three complementary music workflows: **songwriting craft** (lyrics, structure, Suno prompts), **AI music generation** (HeartMuLa open-source), and **audio analysis** (spectrograms, features). Choose based on what the user needs.

| User wants... | Section |
|--------------|---------|
| Write song lyrics, parody, or Suno prompts | § Songwriting Craft |
| Generate music from text/lyrics with AI | § HeartMuLa Generation |
| Visualize audio (spectrograms, MFCC, chroma) | § Audio Analysis |

---

## Songwriting Craft

Everything here is a GUIDELINE, not a rule. Art breaks rules on purpose.

### Song Structure

Common skeletons — mix, modify, or throw out:

```
ABABCB  Verse/Chorus/Verse/Chorus/Bridge/Chorus    (most pop/rock)
AABA    Verse/Verse/Bridge/Verse                    (jazz standards, ballads)
ABAB    Verse/Chorus alternating                    (simple, direct)
AAA     Verse/Verse/Verse (strophic)                (folk, storytelling)
```

Building blocks: Intro, Verse, Pre-Chorus, Chorus, Bridge, Outro. You don't need all of these.

### Rhyme, Meter, and Sound

**Rhyme types** (tight to loose): Perfect (lean/mean), Family (crate/braid), Assonance (had/glass), Consonance (scene/when), Near/slant. Mix them — all perfect rhymes sound like nursery rhymes.

**Internal rhyme:** Rhyming within a line, not just at ends.

**Meter:** Stressed syllables matter more than total count. Say it out loud. If you stumble, the meter needs work.

### Emotional Arc and Dynamics

Energy mapping: Intro 2-3 → Verse 5-6 → Pre-Chorus 7 → Chorus 8-9 → Bridge varies → Final Chorus 9-10.

Most powerful trick: **CONTRAST.** Whisper before a scream. Sparse before dense. Silence is an instrument.

### Writing Lyrics

- **Show, don't tell:** "Your hoodie's still on the hook by the door" > "I was sad"
- **The hook:** The line people remember. Place where it lands hardest.
- **Prosody:** Stable feelings pair with settled melodies; unstable feelings with wandering melodies.
- **Avoid:** Cliches on autopilot, forced word order for rhyme, same energy in every section.

### Parody and Adaptation

1. Map the original's structure (syllables, rhyme scheme, stressed syllables)
2. Match stressed syllables to same beats as original
3. On long held notes, match the VOWEL SOUND
4. Monosyllabic swaps keep rhythm intact (Crime → Code, Snake → Noose)
5. Keep some original lines intact for recognizability

### Suno AI Prompt Engineering

**Style field formula:** Genre + Mood + Era + Instruments + Vocal Style + Production + Dynamics

```
BAD:  "sad rock song"
GOOD: "Cinematic orchestral spy thriller, 1960s Cold War era, smoky
       sultry female vocalist, big band jazz, brass section with
       trumpets and french horns, sweeping strings, minor key"
```

**Describe the journey, not just the genre.** "Begins as haunting whisper over sparse piano. Gradually layers in muted brass. Builds through chorus with full orchestra."

**Metatags** (in [brackets] inside lyrics): [Verse], [Chorus], [Bridge], [Whispered], [Belted], [High Energy], [Emotional Climax], [Female Vocals], etc.

**Phonetic tricks for AI singers:**
- Spell words as they sound: "through" → "thru"
- ALL CAPS = louder, vowel extension: "lo-o-o-ove"
- Spell out numbers: "24/7" → "twenty four seven"
- Space acronyms: "AI" → "A I"

---

## HeartMuLa Generation

HeartMuLa is an open-source music foundation model (Apache-2.0) that generates full songs from lyrics + tags. Comparable to Suno.

### Hardware Requirements

- **Minimum:** 8GB VRAM with `--lazy_load true`
- **Recommended:** 16GB+ VRAM
- **CPU mode:** Possible but extremely slow (30-60+ min per song)

### Installation

```bash
cd ~/
git clone https://github.com/HeartMuLa/heartlib.git
cd heartlib
uv venv --python 3.10 .venv
. .venv/bin/activate
uv pip install -e .
uv pip install --upgrade datasets transformers
```

**Required patches** (for transformers 5.x):
1. RoPE cache fix in `src/heartlib/heartmula/modeling_heartmula.py` — add RoPE reinitialization after `reset_caches` try/except
2. HeartCodec loading fix — add `ignore_mismatched_sizes=True` to all `HeartCodec.from_pretrained()` calls

### Download models

```bash
hf download --local-dir './ckpt' 'HeartMuLa/HeartMuLaGen'
hf download --local-dir './ckpt/HeartMuLa-oss-3B' 'HeartMuLa/HeartMuLa-oss-3B-happy-new-year'
hf download --local-dir './ckpt/HeartCodec-oss' 'HeartMuLa/HeartCodec-oss-20260123'
```

### Usage

```bash
python ./examples/run_music_generation.py \
  --model_path=./ckpt \
  --version="3B" \
  --lyrics="./assets/lyrics.txt" \
  --tags="./assets/tags.txt" \
  --save_path="./assets/output.mp3" \
  --lazy_load true
```

**Tags:** comma-separated, no spaces: `piano,happy,wedding,synthesizer,romantic`

**Lyrics:** use bracketed structural tags: `[Intro]`, `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--max_audio_length_ms` | 240000 | Max length (240s = 4 min) |
| `--lazy_load` | false | Load/unload models on demand (saves VRAM) |
| `--mula_dtype` | bfloat16 | bf16 recommended for HeartMuLa |
| `--codec_dtype` | float32 | fp32 recommended for quality |

### Pitfalls

1. Do NOT use bf16 for HeartCodec — degrades audio quality
2. Tags may be ignored — known issue; lyrics tend to dominate
3. RTX 5080 incompatibility reported in upstream issues
4. Dependency pin conflicts require manual upgrades and patches

---

## Audio Analysis

Generate spectrograms and multi-panel audio feature visualizations using [songsee](https://github.com/steipete/songsee).

### Setup

```bash
go install github.com/steipete/songsee/cmd/songsee@latest
```

### Usage

```bash
songsee track.mp3                              # Basic spectrogram
songsee track.mp3 -o spectrogram.png           # Save to file
songsee track.mp3 --viz spectrogram,mel,chroma,hpss,selfsim,loudness,tempogram,mfcc,flux  # Multi-panel
songsee track.mp3 --start 12.5 --duration 8    # Time slice
```

### Visualization Types

| Type | Description |
|------|-------------|
| `spectrogram` | Standard frequency spectrogram |
| `mel` | Mel-scaled spectrogram |
| `chroma` | Pitch class distribution |
| `hpss` | Harmonic/percussive separation |
| `selfsim` | Self-similarity matrix |
| `loudness` | Loudness over time |
| `tempogram` | Tempo estimation |
| `mfcc` | Mel-frequency cepstral coefficients |
| `flux` | Spectral flux (onset detection) |

### Common Flags

| Flag | Description |
|------|-------------|
| `--viz` | Visualization types (comma-separated) |
| `--style` | Color palette: classic, magma, inferno, viridis, gray |
| `--width` / `--height` | Output dimensions |
| `--start` / `--duration` | Time slice |
| `-o` | Output file path |

Output images can be inspected with `vision_analyze` for automated audio analysis.

---

## Lessons Learned

- Describing the dynamic ARC in the style field matters more than listing genres
- A strong vocal persona description makes bigger difference than any single metatag
- Keeping some original lines in parody adds recognizability
- The bridge slot is where you can transform imagery
- Don't be precious about rules — if a line breaks meter but hits harder, keep it
