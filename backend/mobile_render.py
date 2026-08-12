"""Briques serveur pour l'app mobile : analyse BPM et rendu vidéo final (ffmpeg)."""
import re
import subprocess

import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 22050
HOP = 512


def _decode_pcm(path: str, max_s: int = 150) -> np.ndarray:
    cmd = [FF, "-i", path, "-t", str(max_s), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-v", "error", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True, timeout=180).stdout
    return np.frombuffer(raw, dtype=np.float32)


def analyze_bpm(path: str, duration: float | None = None) -> dict:
    """BPM + grille de beats (autocorrélation du flux d'énergie, phase optimisée)."""
    x = _decode_pcm(path)
    if x.size < SR * 3:
        raise ValueError("Audio trop court (3 s minimum)")
    n = x.size // HOP
    rms = np.sqrt((x[: n * HOP].reshape(n, HOP) ** 2).mean(axis=1))
    flux = np.maximum(np.diff(rms), 0)
    flux = flux - flux.mean()
    fps = SR / HOP
    best_score, best_bpm = -1e9, 120.0
    for bpm in np.arange(60, 200.5, 0.5):
        lag = int(round(60.0 / bpm * fps))
        if lag < 4 or lag >= flux.size // 2:
            continue
        score = float((flux[lag:] * flux[:-lag]).sum()) / (flux.size - lag)
        # prior log-normal centré ~125 BPM : évite les erreurs d'octave (60 vs 120)
        prior = float(np.exp(-0.5 * (np.log2(bpm / 125.0) / 0.6) ** 2))
        score *= prior
        if score > best_score:
            best_score, best_bpm = score, float(bpm)
    period = 60.0 / best_bpm
    total = x.size / SR
    best_off, best_e = 0.0, -1e9
    for k in range(32):
        off = k * period / 32
        idx = (np.arange(off, min(total, 60), period) * fps).astype(int)
        idx = idx[idx < flux.size]
        e = float(flux[idx].sum())
        if e > best_e:
            best_e, best_off = e, off
    dur = float(duration or total)
    count = max(0, int((dur - best_off) / period)) + 1
    beats = [round(best_off + i * period, 4) for i in range(min(count, 5000))]
    return {"bpm": round(best_bpm, 2), "first_beat": round(best_off, 4),
            "period": round(period, 5), "duration_analyzed": round(total, 2), "beats": beats}


def ff_duration(path: str) -> float:
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _ass_color(hexc: str) -> str:
    h = (hexc or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}"


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words: list, ext_start: float, dur: float, style: dict, path: str):
    """Sous-titres mode 'mot' (un mot plein écran), mots mis en avant plus gros/colorés."""
    style = style or {}
    base = 120
    color = _ass_color(style.get("color") or "#FFFFFF")
    emph_c = _ass_color(style.get("emphColor") or "#FF453A")
    emph_fs = int(base * float(style.get("emphScale") or 1.45))
    up = (style.get("textCase") or "up") == "up"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, BorderStyle",
        f"Style: Default,Liberation Sans,{base},{color},&H00000000,&H00000000,-1,7,0,5,40,40,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]
    for w in words or []:
        st = float(w.get("start", 0)) - ext_start
        en = float(w.get("end", 0)) - ext_start
        if en <= 0 or st >= dur:
            continue
        st, en = max(0.0, st), min(dur, max(en, st + 0.08))
        txt = str(w.get("text", "")).replace("{", "").replace("}", "").replace("\n", " ")
        if up:
            txt = txt.upper()
        if w.get("emph"):
            txt = f"{{\\fs{emph_fs}\\c{emph_c}}}{txt}"
        lines.append(f"Dialogue: 0,{_ts(st)},{_ts(en)},Default,{txt}")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def build_render_cmd(clip_files: list, audio_file: str, ext_start: float, dur: float,
                     boundaries: list, ass_path: str, out_path: str) -> list:
    """Assemble la commande ffmpeg : segments coupés sur les beats, 1080x1920, sous-titres, son."""
    segs = []
    cursors = [0.0] * len(clip_files)
    durs = [max(ff_duration(f), 0.5) for f in clip_files]
    for i in range(len(boundaries) - 1):
        seg_d = boundaries[i + 1] - boundaries[i]
        if seg_d < 0.03:
            continue
        ci = i % len(clip_files)
        off = cursors[ci] % max(durs[ci] - seg_d, 0.01)
        cursors[ci] += seg_d
        segs.append((ci, off, seg_d))
    segs = segs[:120]
    cmd = [FF, "-y"]
    for f in clip_files:
        cmd += ["-i", f]
    cmd += ["-ss", str(ext_start), "-t", str(dur), "-i", audio_file]
    fc = []
    for k, (ci, off, d) in enumerate(segs):
        fc.append(f"[{ci}:v]trim=start={off:.3f}:duration={d:.3f},setpts=PTS-STARTPTS,"
                  f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30[s{k}]")
    fc.append("".join(f"[s{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[vc]")
    fc.append(f"[vc]ass={ass_path}[vo]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", f"{len(clip_files)}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path]
    return cmd
