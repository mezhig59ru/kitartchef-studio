import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
import time
import json
import shutil
import subprocess
import urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, send_file
from moviepy import (
    AudioFileClip, 
    CompositeAudioClip,
    ImageClip, 
    VideoFileClip, 
    concatenate_videoclips, 
    CompositeVideoClip, 
    vfx,
    afx
)

app = Flask(__name__)
UPLOAD_FOLDER = "web_uploads"
OUTPUT_FOLDER = "web_outputs"
INPUT_DIR = "input_media"
MUSIC_FOLDER = os.path.abspath(os.path.join("static", "audio", "music"))
VOICE_NAME = "ru-RU-DmitryNeural"

TARGET_W, TARGET_H = 1080, 1920
TRANSITION_DURATION = 0.5
ZOOM_FACTOR = 0.12

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(MUSIC_FOLDER, exist_ok=True)

def get_ffmpeg_binary():
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'

# ==============================================================================
# STARTER AUDIO TRACKS & MUSIC MANAGER
# ==============================================================================
STARTER_TRACKS = [
    ("01_lofi_kitchen.mp3", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"),
    ("02_acoustic_cozy.mp3", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"),
    ("03_modern_lounge.mp3", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"),
]

MUSIC_TITLES = {
    "01_lofi_kitchen.mp3": "01. Lo-Fi Kitchen (Кулинарный чилл)",
    "02_acoustic_cozy.mp3": "02. Acoustic Cozy (Уютный акустический)",
    "03_modern_lounge.mp3": "03. Modern Lounge (Современный лаунж)",
}

def ensure_starter_tracks():
    try:
        os.makedirs(MUSIC_FOLDER, exist_ok=True)
        existing = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
        if not existing:
            for filename, url in STARTER_TRACKS:
                dest = os.path.join(MUSIC_FOLDER, filename)
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response, open(dest, 'wb') as out_f:
                        shutil.copyfileobj(response, out_f)
                except Exception:
                    # Fallback synthetic tone if offline
                    try:
                        ffmpeg_exe = get_ffmpeg_binary()
                        subprocess.run([
                            ffmpeg_exe, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=15",
                            "-c:a", "libmp3lame", "-b:a", "128k", dest
                        ], capture_output=True, check=False)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[Music] ensure_starter_tracks error: {e}")

# Call on import to guarantee tracks
ensure_starter_tracks()

# ==============================================================================
# EDGE-TTS VOICES CONFIGURATION & SYNTHESIS
# ==============================================================================
VOICE_CONFIG = {
    "ru-RU-DmitryNeural": {"voice": "ru-RU-DmitryNeural", "rate": None},
    "ru-RU-SvetlanaNeural": {"voice": "ru-RU-SvetlanaNeural", "rate": None},
    "ru-RU-DenisNeural": {"voice": "ru-RU-DmitryNeural", "rate": "+10%"},
    "ru-RU-DariyaNeural": {"voice": "ru-RU-SvetlanaNeural", "rate": "-5%"},
}

def synthesize_voice(text: str, output_path: str, voice_name: str = "ru-RU-DmitryNeural", retries: int = 4):
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except OSError: pass

    voice_cfg = VOICE_CONFIG.get(voice_name, {"voice": voice_name or "ru-RU-DmitryNeural", "rate": None})
    target_voice = voice_cfg["voice"]
    rate_opt = voice_cfg.get("rate")

    cmd = [
        "edge-tts",
        "--voice", target_voice,
        "--text", text,
        "--write-media", output_path
    ]
    if rate_opt:
        cmd.extend(["--rate", rate_opt])

    for attempt in range(1, retries + 1):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        # If alternative voice failed, try fallback to DmitryNeural
        if target_voice != "ru-RU-DmitryNeural":
            fb_cmd = ["edge-tts", "--voice", "ru-RU-DmitryNeural", "--text", text, "--write-media", output_path]
            fb_res = subprocess.run(fb_cmd, capture_output=True, text=True)
            if fb_res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                return True
        time.sleep(1.0)

    raise RuntimeError("Сервер озвучки временно не ответил. Нажмите сборку еще раз через 3 секунды.")

def synthesize_dmitry_voice(text: str, output_path: str, retries: int = 5):
    return synthesize_voice(text, output_path, "ru-RU-DmitryNeural", retries)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_music_list', methods=['GET'])
def get_music_list():
    try:
        ensure_starter_tracks()
        tracks = []
        if os.path.exists(MUSIC_FOLDER):
            for f in sorted(os.listdir(MUSIC_FOLDER)):
                if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.aac')):
                    title = MUSIC_TITLES.get(f, f"🎵 {os.path.splitext(f)[0].replace('_', ' ').title()}")
                    tracks.append({
                        'filename': f,
                        'title': title
                    })
        return jsonify({'status': 'ok', 'tracks': tracks})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/upload_music', methods=['POST'])
def upload_music():
    try:
        f = request.files.get('file') or request.files.get('music_file')
        if not f or f.filename == '':
            return jsonify({'status': 'error', 'message': 'Файл музыки не выбран'}), 400

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ('.mp3', '.wav', '.m4a', '.ogg', '.aac'):
            return jsonify({'status': 'error', 'message': 'Поддерживаются аудиофайлы: MP3, WAV, M4A, OGG, AAC'}), 400

        safe_name = secure_filename(f.filename)
        if not safe_name:
            safe_name = f"custom_track_{int(time.time())}{ext}"

        target_path = os.path.join(MUSIC_FOLDER, safe_name)
        base_name, file_ext = os.path.splitext(safe_name)
        counter = 1
        while os.path.exists(target_path):
            safe_name = f"{base_name}_{counter}{file_ext}"
            target_path = os.path.join(MUSIC_FOLDER, safe_name)
            counter += 1

        f.save(target_path)
        display_title = f"🎵 {base_name.replace('_', ' ').title()}"
        MUSIC_TITLES[safe_name] = display_title

        return jsonify({
            'status': 'ok',
            'filename': safe_name,
            'title': display_title
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/render_reel', methods=['POST'])
def render_reel():
    try:
        dish_name = request.form.get('dish_name', 'Рецепт')
        voice_text = request.form.get('voice_text', '').strip()
        voice_speaker = request.form.get('voice_speaker', 'ru-RU-DmitryNeural').strip()
        post_kit_text = request.form.get('post_kit', '').strip()
        subtitles = json.loads(request.form.get('subtitles', '[]'))
        files = request.files.getlist('media_files')
        custom_audio = request.files.get('custom_audio')

        bg_music_enabled = request.form.get('bg_music_enabled', 'false').lower() in ('true', '1', 'on', 'yes')
        bg_music_track = request.form.get('bg_music_track', '').strip()
        try:
            bg_music_volume = float(request.form.get('bg_music_volume', 0.15))
        except (ValueError, TypeError):
            bg_music_volume = 0.15
        bg_music_volume = max(0.05, min(0.40, bg_music_volume))

        if not files:
            return jsonify({'status': 'error', 'message': 'Кадры не загружены'}), 400

        saved_paths = []
        for idx, f in enumerate(files):
            ext = os.path.splitext(f.filename)[1]
            target_path = os.path.join(UPLOAD_FOLDER, f"clip_{idx}{ext}")
            f.save(target_path)
            saved_paths.append(target_path)

        voice_file = os.path.join(UPLOAD_FOLDER, "temp_voice.mp3")
        if custom_audio and custom_audio.filename != '':
            custom_audio.save(voice_file)
        else:
            synthesize_voice(voice_text, voice_file, voice_name=voice_speaker)

        voice_audio = AudioFileClip(voice_file)
        total_duration = voice_audio.duration

        # Background music mixing with audio ducking
        music_clips_to_close = []
        if bg_music_enabled and bg_music_track:
            safe_track = os.path.basename(bg_music_track)
            track_path = os.path.join(MUSIC_FOLDER, safe_track)
            if os.path.exists(track_path):
                try:
                    raw_music = AudioFileClip(track_path)
                    music_clips_to_close.append(raw_music)
                    if raw_music.duration < total_duration:
                        looped_music = raw_music.with_effects([afx.AudioLoop(duration=total_duration)])
                    else:
                        looped_music = raw_music.subclipped(0, total_duration)

                    fade_dur = min(1.5, max(0.5, total_duration * 0.15))
                    processed_music = looped_music.with_effects([
                        afx.MultiplyVolume(bg_music_volume),
                        afx.AudioFadeOut(fade_dur)
                    ])
                    music_clips_to_close.append(processed_music)
                    final_audio = CompositeAudioClip([voice_audio, processed_music])
                except Exception as music_err:
                    print(f"[Music Mixing Warning] {music_err}, using voice only")
                    final_audio = voice_audio
            else:
                final_audio = voice_audio
        else:
            final_audio = voice_audio

        num_clips = len(saved_paths)
        num_transitions = num_clips - 1
        clip_duration = (total_duration + (num_transitions * TRANSITION_DURATION)) / num_clips

        clips = []
        for i, path in enumerate(saved_paths):
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png'):
                base_clip = ImageClip(path).with_duration(clip_duration)
                base_clip = base_clip.resized(height=TARGET_H)
                if base_clip.w < TARGET_W:
                    base_clip = base_clip.resized(width=TARGET_W)
                base_clip = base_clip.cropped(x_center=base_clip.w / 2, y_center=base_clip.h / 2, width=TARGET_W, height=TARGET_H)
                processed_clip = base_clip.resized(lambda t: 1.0 + ZOOM_FACTOR * (t / clip_duration))
                processed_clip = processed_clip.cropped(x_center=TARGET_W / 2, y_center=TARGET_H / 2, width=TARGET_W, height=TARGET_H)
            else:
                v = VideoFileClip(path)
                base_clip = v.subclipped(0, clip_duration) if v.duration > clip_duration else v.with_duration(clip_duration)
                base_clip = base_clip.without_audio()
                base_clip = base_clip.resized(height=TARGET_H)
                if base_clip.w < TARGET_W:
                    base_clip = base_clip.resized(width=TARGET_W)
                processed_clip = base_clip.cropped(x_center=base_clip.w / 2, y_center=base_clip.h / 2, width=TARGET_W, height=TARGET_H)

            if i > 0:
                processed_clip = processed_clip.with_effects([vfx.CrossFadeIn(TRANSITION_DURATION)])
            clips.append(processed_clip)

        base_video = concatenate_videoclips(clips, method="compose", padding=-TRANSITION_DURATION)

        def make_sub_image(text):
            img = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arialbd.ttf", 52)
            except IOError:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = (TARGET_W - tw) / 2, 1250

            draw.rounded_rectangle([x - 28, y - 16, x + tw + 28, y + th + 16], radius=18, fill=(0, 0, 0, 160))
            for ox in range(-3, 4):
                for oy in range(-3, 4):
                    draw.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), text, font=font, fill=(255, 220, 0, 255))
            return np.array(img)

        step = clip_duration - TRANSITION_DURATION
        sub_clips = []
        for i in range(num_clips):
            text = subtitles[i] if i < len(subtitles) and subtitles[i].strip() else ""
            if not text:
                continue
            start_t = i * step
            dur_t = max(0.1, total_duration - start_t) if i == num_clips - 1 else step
            sub_clips.append(ImageClip(make_sub_image(text)).with_start(start_t).with_duration(dur_t))

        final_video = CompositeVideoClip([base_video] + sub_clips).with_audio(final_audio)
        output_filename = "latest_reel.mp4"
        output_filepath = os.path.join(OUTPUT_FOLDER, output_filename)

        final_video.write_videofile(
            output_filepath,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast"
        )

        post_filename = "post_kit.txt"
        post_filepath = os.path.join(OUTPUT_FOLDER, post_filename)
        with open(post_filepath, "w", encoding="utf-8") as pf:
            pf.write(f"БЛЮДО: {dish_name}\n")
            pf.write(f"ГОЛОС: {voice_speaker}\n")
            pf.write(f"ДИКТОР: {voice_text}\n\n")
            pf.write("="*50 + "\n")
            pf.write("МАТЕРИАЛЫ ДЛЯ ПУБЛИКАЦИИ:\n")
            pf.write("="*50 + "\n\n")
            pf.write(post_kit_text if post_kit_text else "Тексты постов не были переданы.")

        voice_audio.close()
        for mc in music_clips_to_close:
            try: mc.close()
            except Exception: pass
        base_video.close()
        final_video.close()
        for c in clips:
            c.close()

        return jsonify({
            'status': 'ok',
            'video_url': f'/get_video/{output_filename}',
            'post_kit_url': f'/get_video/{post_filename}'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/export_speed', methods=['POST'])
def export_speed():
    try:
        data = request.get_json(silent=True) or {}
        speed = float(data.get('speed', 1.0))

        if speed < 0.5 or speed > 2.0:
            return jsonify({'status': 'error', 'message': 'Коэффициент скорости должен быть в пределах от 0.5 до 2.0'}), 400

        input_video = os.path.abspath(os.path.join(OUTPUT_FOLDER, "latest_reel.mp4"))
        if not os.path.exists(input_video):
            return jsonify({'status': 'error', 'message': 'Исходное видео latest_reel.mp4 не найдено. Сначала смонтируйте ролик.'}), 404

        output_filename = "latest_reel_speed.mp4"
        output_filepath = os.path.abspath(os.path.join(OUTPUT_FOLDER, output_filename))

        pts_factor = round(1.0 / float(speed), 6)
        filter_complex = f"[0:v]setpts={pts_factor}*PTS[v];[0:a]atempo={speed}[a]"

        ffmpeg_exe = get_ffmpeg_binary()
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            output_filepath
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err_msg = result.stderr[-300:] if result.stderr else "Ошибка FFmpeg"
            return jsonify({'status': 'error', 'message': f'Сбой обработки FFmpeg: {err_msg}'}), 500

        if not os.path.exists(output_filepath) or os.path.getsize(output_filepath) < 1000:
            return jsonify({'status': 'error', 'message': 'Файл ускоренного видео не был сформирован.'}), 500

        speed_str = f"{speed:g}"
        return send_file(
            output_filepath,
            as_attachment=True,
            download_name=f"kitartchef_{speed_str}x.mp4",
            mimetype="video/mp4",
            max_age=0
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/adjust_speed', methods=['POST'])
def adjust_speed():
    try:
        data = request.get_json(silent=True) or {}
        speed = float(data.get('speed', 1.0))

        if speed < 0.5 or speed > 2.0:
            return jsonify({'status': 'error', 'message': 'Коэффициент скорости должен быть в пределах от 0.5 до 2.0'}), 400

        input_video = os.path.join(OUTPUT_FOLDER, 'latest_reel.mp4')
        if not os.path.exists(input_video):
            return jsonify({'status': 'error', 'message': 'Исходное видео latest_reel.mp4 не найдено. Сначала смонтируйте ролик.'}), 404

        output_filename = 'latest_reel_speed.mp4'
        output_filepath = os.path.join(OUTPUT_FOLDER, output_filename)

        pts_factor = 1.0 / speed
        filter_complex = f'[0:v]setpts={pts_factor:.6f}*PTS[v];[0:a]atempo={speed:.4f}[a]'

        ffmpeg_exe = get_ffmpeg_binary()
        cmd = [
            ffmpeg_exe,
            '-y',
            '-i', input_video,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-c:a', 'aac',
            output_filepath
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err_msg = result.stderr[-300:] if result.stderr else 'Ошибка FFmpeg'
            return jsonify({'status': 'error', 'message': f'Сбой обработки FFmpeg: {err_msg}'}), 500

        speed_str = f'{speed:g}'
        return jsonify({
            'status': 'ok',
            'speed': speed,
            'video_url': f'/get_video/{output_filename}',
            'download_url': f'/get_video/{output_filename}',
            'filename': f'latest_reel_{speed_str}x.mp4'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_video/<filename>')
def get_video(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=False)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("STUDIO RUNNING: http://127.0.0.1:5000")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=5000, debug=False)
