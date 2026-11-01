import os
import sys
import time
import json
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, jsonify, render_template_string, send_file
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
# ВЕБ-ИНТЕРФЕЙС С ЭКСПРЕСС-ИМПОРТОМ И 5 СУБТИТРАМИ
# ==============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Culinary Reels Studio Pro</title>
    <style>
        :root {
            --bg-primary: #0f1117;
            --bg-secondary: #1a1d27;
            --card-bg: #232736;
            --accent: #ff6b35;
            --accent-hover: #ff8552;
            --text-main: #f0f2f5;
            --text-muted: #9aa0a6;
            --border: #33384a;
            --bot-color: #3b82f6;
            --bot-hover: #2563eb;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg-primary); color: var(--text-main); padding: 30px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 920px; display: flex; flex-direction: column; gap: 20px; }
        
        header { text-align: center; margin-bottom: 4px; }
        header h1 { font-size: 26px; font-weight: 700; color: #fff; margin-bottom: 4px; }
        header p { color: var(--text-muted); font-size: 13px; }

        .card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
        .card h2 { font-size: 16px; margin-bottom: 12px; color: var(--accent); display: flex; align-items: center; gap: 8px; }

        .form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
        label { font-size: 12px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        input[type="text"], textarea {
            background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
            color: #fff; padding: 10px 12px; font-size: 14px; outline: none; transition: 0.2s;
        }
        input[type="text"]:focus, textarea:focus { border-color: var(--accent); }

        .bot-paste-box {
            background: rgba(59, 130, 246, 0.05); border: 1px dashed var(--bot-color);
            border-radius: 10px; padding: 14px; margin-bottom: 14px;
        }
        .bot-paste-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .bot-paste-header span { font-size: 13px; font-weight: 700; color: var(--bot-color); }
        .bot-btn {
            background: var(--bot-color); color: #fff; border: none; border-radius: 6px;
            padding: 6px 14px; font-size: 12px; font-weight: 700; cursor: pointer; transition: 0.2s;
        }
        .bot-btn:hover { background: var(--bot-hover); }

        .subtitles-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
        .subtitles-grid input { text-align: center; font-size: 11px; font-weight: 700; text-transform: uppercase; }

        .dropzone {
            border: 2px dashed var(--border); border-radius: 12px; padding: 26px 16px;
            text-align: center; cursor: pointer; transition: 0.2s; background: rgba(255,255,255,0.01);
        }
        .dropzone:hover, .dropzone.dragover { border-color: var(--accent); background: rgba(255,107,53,0.04); }
        .dropzone span { color: var(--text-muted); font-size: 13px; }

        .preview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 14px; }
        .media-card {
            background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
            height: 165px; overflow: hidden; position: relative; cursor: grab; user-select: none;
            display: flex; align-items: center; justify-content: center;
        }
        .media-card:active { cursor: grabbing; }
        .media-card.dragging { opacity: 0.4; border: 2px dashed var(--accent); }
        .media-card img, .media-card video { width: 100%; height: 100%; object-fit: cover; }
        .badge {
            position: absolute; top: 6px; left: 6px; background: rgba(0,0,0,0.8);
            color: #fff; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;
        }

        button.primary-btn {
            background: var(--accent); color: #fff; border: none; border-radius: 10px;
            padding: 15px; font-size: 15px; font-weight: 700; cursor: pointer; transition: 0.2s;
            width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        button.primary-btn:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }

        #statusBox { display: none; text-align: center; padding: 14px; font-size: 14px; color: var(--accent); font-weight: 600; }
        #resultCard { display: none; }
        video#resultPlayer { width: 100%; max-height: 480px; border-radius: 10px; background: #000; margin-top: 10px; }
        .download-row { display: flex; gap: 10px; justify-content: center; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🍳 Reels Studio Pro</h1>
            <p>Автономный монтаж кулинарных роликов для @KitArtChef (чистый голос)</p>
        </header>

        <div class="card">
            <h2>1. Сценарий и параметры ролика</h2>

            <div class="bot-paste-box">
                <div class="bot-paste-header">
                    <span>⚡ Экспресс-вставка ответа из Gem-бота:</span>
                    <button class="bot-btn" type="button" onclick="parseBotResponse()">Заполнить форму</button>
                </div>
                <textarea id="rawBotInput" rows="3" placeholder="Вставьте сюда Блок 1 из Gem-бота и нажмите 'Заполнить форму'"></textarea>
            </div>

            <div class="form-group">
                <label>Название блюда:</label>
                <input type="text" id="dishName" value="Яблочный крамбл">
            </div>

            <div class="form-group">
                <label>Текст диктора Дмитрия (40–44 слова):</label>
                <textarea id="voiceText" rows="2">Хватит сушить крамбл в духовке сорок минут! На одной сковороде карамелизуем яблоки с корицей а овсяную крошку обжариваем отдельно на сливочном масле. Соединяем слои перед подачей с ледяным пломбиром. Точные пропорции ждут вас в описании.</textarea>
            </div>

            <div class="form-group">
                <label>5 субтитров под 5 кадров (синхронно):</label>
                <div class="subtitles-grid">
                    <input type="text" id="sub0" value="БЕЗ ДУХОВКИ">
                    <input type="text" id="sub1" value="ЯБЛОКИ И ХЛОПЬЯ">
                    <input type="text" id="sub2" value="КАРАМЕЛИЗАЦИЯ">
                    <input type="text" id="sub3" value="ЗВОНКИЙ ХРУСТ">
                    <input type="text" id="sub4" value="РЕЦЕПТ ВНИЗУ">
                </div>
            </div>

            <div class="form-group">
                <label>Своя аудиодорожка (необязательно):</label>
                <input type="file" id="customAudioInput" accept="audio/*">
            </div>

            <input type="hidden" id="fullPostKit" value="">
        </div>

        <div class="card">
            <h2>2. Кадры блюда (перетащите 5 файлов)</h2>
            <div class="dropzone" id="dropzone">
                <span>Перетащите сюда 5 фото или 1 видео Flow + 4 фото</span>
                <input type="file" id="fileInput" multiple accept="image/*,video/*" style="display:none">
            </div>
            <div class="preview-grid" id="previewGrid"></div>
        </div>

        <button class="primary-btn" id="generateBtn" onclick="startGeneration()">
            Смонтировать вертикальный Reel (20 сек)
        </button>

        <div id="statusBox">⏳ Генерация голоса Дмитрия, нарезка кадров и сборка...</div>

        <div class="card" id="resultCard">
            <h2>🎉 Результат готов</h2>
            <video id="resultPlayer" controls></video>
            <div class="download-row">
                <a id="downloadLink" class="primary-btn" style="width:auto; padding:10px 24px; text-decoration:none;" download>
                    Скачать MP4
                </a>
                <a id="downloadPostKit" class="primary-btn" style="width:auto; padding:10px 24px; text-decoration:none; background:#3b82f6;" download="post_kit.txt">
                    Скачать тексты постов (ТГ/Shorts)
                </a>
            </div>
        </div>
    </div>

    <script>
        let uploadedFiles = [];
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('fileInput');
        const previewGrid = document.getElementById('previewGrid');

        function parseBotResponse() {
            const raw = document.getElementById('rawBotInput').value;
            if (!raw.trim()) {
                alert('Вставьте текст ответа Gem-бота в поле!');
                return;
            }

            const dishMatch = raw.match(/\\[DISH_NAME\\]\\s*\\n+([^\\n\\[]+)/i);
            if (dishMatch) document.getElementById('dishName').value = dishMatch[1].trim();

            const voiceMatch = raw.match(/\\[VOICE_TEXT\\]\\s*\\n+([^\\[]+?)(?=\\n\\s*\\[|$)/is);
            if (voiceMatch) document.getElementById('voiceText').value = voiceMatch[1].trim().replace(/\\n+/g, ' ');

            const subMatch = raw.match(/\\[SUBTITLES\\]\\s*\\n+([^\\[]+?)(?=\\n\\s*---|$)/is);
            if (subMatch) {
                const lines = subMatch[1].split('\\n')
                    .map(l => l.replace(/^[0-9\\.\\-\\)\\*\\s]+/, '').trim())
                    .filter(l => l.length > 0);
                for (let i = 0; i < 5; i++) {
                    if (lines[i]) document.getElementById(`sub${i}`).value = lines[i].toUpperCase();
                }
            }

            const postMatch = raw.match(/(###\\s*БЛОК\\s*3.*?$)/is);
            if (postMatch) {
                document.getElementById('fullPostKit').value = postMatch[1].trim();
            } else {
                document.getElementById('fullPostKit').value = raw;
            }

            alert('✓ Форма успешно заполнена!');
        }

        dropzone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => handleFiles(Array.from(e.target.files));
        dropzone.ondragover = (e) => { e.preventDefault(); dropzone.classList.add('dragover'); };
        dropzone.ondragleave = () => dropzone.classList.remove('dragover');
        dropzone.ondrop = (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            handleFiles(Array.from(e.dataTransfer.files));
        };

        function handleFiles(files) {
            const valid = files.filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
            uploadedFiles = valid.slice(0, 5);
            renderGrid();
        }

        function renderGrid() {
            previewGrid.innerHTML = '';
            uploadedFiles.forEach((file, index) => {
                const card = document.createElement('div');
                card.className = 'media-card';
                card.draggable = true;
                card.dataset.index = index;

                const badge = document.createElement('div');
                badge.className = 'badge';
                badge.textContent = `Кадр ${index + 1}`;
                card.appendChild(badge);

                const url = URL.createObjectURL(file);
                if (file.type.startsWith('image/')) {
                    const img = document.createElement('img');
                    img.src = url;
                    card.appendChild(img);
                } else {
                    const vid = document.createElement('video');
                    vid.src = url;
                    card.appendChild(vid);
                }

                card.ondragstart = (e) => {
                    card.classList.add('dragging');
                    e.dataTransfer.setData('text/plain', index);
                };
                card.ondragend = () => card.classList.remove('dragging');
                card.ondragover = (e) => e.preventDefault();
                card.ondrop = (e) => {
                    e.preventDefault();
                    const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
                    const toIdx = index;
                    const movedItem = uploadedFiles.splice(fromIdx, 1)[0];
                    uploadedFiles.splice(toIdx, 0, movedItem);
                    renderGrid();
                };
                previewGrid.appendChild(card);
            });
        }

        async function startGeneration() {
            if (uploadedFiles.length === 0) {
                alert('Загрузите 5 кадров для монтажа!');
                return;
            }

            const btn = document.getElementById('generateBtn');
            const status = document.getElementById('statusBox');
            const resultCard = document.getElementById('resultCard');

            btn.disabled = true;
            status.style.display = 'block';
            resultCard.style.display = 'none';

            const formData = new FormData();
            formData.append('dish_name', document.getElementById('dishName').value);
            formData.append('voice_text', document.getElementById('voiceText').value);
            formData.append('post_kit', document.getElementById('fullPostKit').value);

            const subs = [
                document.getElementById('sub0').value,
                document.getElementById('sub1').value,
                document.getElementById('sub2').value,
                document.getElementById('sub3').value,
                document.getElementById('sub4').value
            ];
            formData.append('subtitles', JSON.stringify(subs));

            const customAudio = document.getElementById('customAudioInput').files[0];
            if (customAudio) formData.append('custom_audio', customAudio);

            uploadedFiles.forEach((file, idx) => {
                formData.append('media_files', file, `file_${idx}_${file.name}`);
            });

            try {
                const res = await fetch('/render_reel', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.status === 'ok') {
                    const player = document.getElementById('resultPlayer');
                    const link = document.getElementById('downloadLink');
                    const postLink = document.getElementById('downloadPostKit');
                    
                    player.src = data.video_url + '?t=' + new Date().getTime();
                    link.href = data.video_url;
                    postLink.href = data.post_kit_url;
                    resultCard.style.display = 'block';
                } else {
                    alert('Ошибка монтажа: ' + data.message);
                }
            } catch (err) {
                alert('Сбой связи с сервером: ' + err);
            } finally {
                btn.disabled = false;
                status.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

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
    return render_template_string(HTML_TEMPLATE)

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