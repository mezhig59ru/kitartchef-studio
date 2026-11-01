import os
import sys
import time
import json
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, jsonify, render_template, send_file
from moviepy import (
    AudioFileClip, 
    ImageClip, 
    VideoFileClip, 
    concatenate_videoclips, 
    CompositeVideoClip, 
    vfx
)

app = Flask(__name__)
UPLOAD_FOLDER = "web_uploads"
OUTPUT_FOLDER = "web_outputs"
INPUT_DIR = "input_media"
VOICE_NAME = "ru-RU-DmitryNeural"

TARGET_W, TARGET_H = 1080, 1920
TRANSITION_DURATION = 0.5
ZOOM_FACTOR = 0.12

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)

# ==============================================================================
# БЭКЕНД: ЧИСТЫЙ ГОЛОС ДМИТРИЯ БЕЗ СТАРОЙ ПОДМЕНЫ
# ==============================================================================
def synthesize_dmitry_voice(text: str, output_path: str, retries: int = 5):
    if os.path.exists(output_path):
        try: os.remove(output_path)
        except OSError: pass

    cmd = [
        "edge-tts",
        "--voice", VOICE_NAME,
        "--text", text,
        "--write-media", output_path
    ]

    for attempt in range(1, retries + 1):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        time.sleep(1.5)

    raise RuntimeError("Сервер озвучки временно не ответил. Нажмите сборку еще раз через 3 секунды.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/render_reel', methods=['POST'])
def render_reel():
    try:
        dish_name = request.form.get('dish_name', 'Рецепт')
        voice_text = request.form.get('voice_text', '').strip()
        post_kit_text = request.form.get('post_kit', '').strip()
        subtitles = json.loads(request.form.get('subtitles', '[]'))
        files = request.files.getlist('media_files')
        custom_audio = request.files.get('custom_audio')

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
            synthesize_dmitry_voice(voice_text, voice_file)

        voice_audio = AudioFileClip(voice_file)
        total_duration = voice_audio.duration
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
            pf.write(f"ДИКТОР: {voice_text}\n\n")
            pf.write("="*50 + "\n")
            pf.write("МАТЕРИАЛЫ ДЛЯ ПУБЛИКАЦИИ:\n")
            pf.write("="*50 + "\n\n")
            pf.write(post_kit_text if post_kit_text else "Тексты постов не были переданы.")

        voice_audio.close()
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

@app.route('/get_video/<filename>')
def get_video(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=False)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 СТУДИЯ ЗАПУЩЕНА: http://127.0.0.1:5000")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=5000, debug=False)
