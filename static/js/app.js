/**
 * Culinary Reels Studio Pro - Interactive UI & Media Slots Controller
 */

// State: 5 scene slots (null or File object)
const TOTAL_SLOTS = 5;
let sceneSlots = new Array(TOTAL_SLOTS).fill(null);
let targetReplaceSlotIndex = null;
let progressInterval = null;

// DOM Elements
const toastContainer = document.getElementById('toastContainer');
const sceneSlotsGrid = document.getElementById('sceneSlotsGrid');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const slotReplaceInput = document.getElementById('slotReplaceInput');
const bulkUploadBtn = document.getElementById('bulkUploadBtn');
const clearAllSlotsBtn = document.getElementById('clearAllSlotsBtn');
const customAudioInput = document.getElementById('customAudioInput');
const customAudioPlaceholder = document.getElementById('customAudioPlaceholder');

// ==============================================================================
// 1. ELEGANT CUSTOM TOAST NOTIFICATION SYSTEM
// ==============================================================================
function showToast(message, type = 'info', duration = 4000) {
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    else if (type === 'error') icon = '⚠️';
    else if (type === 'warning') icon = '🔔';

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">${escapeHtml(message)}</div>
        <button class="toast-close" type="button" aria-label="Закрыть">&times;</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    const dismiss = () => {
        toast.classList.add('toast-hiding');
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 200);
    };

    closeBtn.onclick = dismiss;
    toastContainer.appendChild(toast);

    if (duration > 0) {
        setTimeout(dismiss, duration);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Override or bridge window.alert to toast
window.alert = function (msg) {
    showToast(msg, 'warning');
};

// ==============================================================================
// 2. GEM BOT EXPRESS PARSER
// ==============================================================================
function parseBotResponse() {
    const rawInput = document.getElementById('rawBotInput');
    const raw = rawInput ? rawInput.value : '';
    if (!raw.trim()) {
        showToast('Вставьте текст ответа Gem-бота в поле экспресс-вставки!', 'warning');
        return;
    }

    let fieldsUpdated = 0;

    // 1. Dish Name
    const dishMatch = raw.match(/\[DISH_NAME\]\s*\n+([^\[\n]+)/i);
    if (dishMatch) {
        const dishEl = document.getElementById('dishName');
        if (dishEl) {
            dishEl.value = dishMatch[1].trim();
            fieldsUpdated++;
        }
    }

    // 2. Voice Text
    const voiceMatch = raw.match(/\[VOICE_TEXT\]\s*\n+([^\[]+?)(?=\n\s*\[|$)/is);
    if (voiceMatch) {
        const voiceEl = document.getElementById('voiceText');
        if (voiceEl) {
            voiceEl.value = voiceMatch[1].trim().replace(/\n+/g, ' ');
            updateVoiceWordCount();
            fieldsUpdated++;
        }
    }

    // 3. 5 Subtitles
    const subMatch = raw.match(/\[SUBTITLES\]\s*\n+([^\[]+?)(?=\n\s*---|$)/is);
    if (subMatch) {
        const lines = subMatch[1].split('\n')
            .map(l => l.replace(/^[0-9\.\-\)\*\s]+/, '').trim())
            .filter(l => l.length > 0);
        for (let i = 0; i < 5; i++) {
            const subInput = document.getElementById(`sub${i}`);
            if (subInput && lines[i]) {
                subInput.value = lines[i].toUpperCase();
                fieldsUpdated++;
            }
        }
    }

    // 4. Post Kit
    const postMatch = raw.match(/(###\s*БЛОК\s*3.*?$)/is);
    const postEl = document.getElementById('fullPostKit');
    if (postEl) {
        postEl.value = postMatch ? postMatch[1].trim() : raw;
    }

    showToast(`✓ Форма успешно заполнена! (${fieldsUpdated} полей обновлено)`, 'success');
}

function updateVoiceWordCount() {
    const voiceEl = document.getElementById('voiceText');
    const counterEl = document.getElementById('voiceWordCount');
    if (!voiceEl || !counterEl) return;

    const words = voiceEl.value.trim().split(/\s+/).filter(w => w.length > 0);
    const count = words.length;
    counterEl.textContent = `${count} слов(а) • цель: 40–44`;
    if (count >= 38 && count <= 46) {
        counterEl.style.color = 'var(--success-border)';
    } else {
        counterEl.style.color = 'var(--text-muted)';
    }
}

// ==============================================================================
// 3. 5-SLOT MEDIA MANAGER (DRAG-AND-DROP, REORDER, REPLACE, DELETE)
// ==============================================================================
function initSlots() {
    renderSlots();
    setupDropzoneListeners();
    setupAudioInputListener();
    const voiceEl = document.getElementById('voiceText');
    if (voiceEl) {
        voiceEl.addEventListener('input', updateVoiceWordCount);
        updateVoiceWordCount();
    }
}

function renderSlots() {
    if (!sceneSlotsGrid) return;
    sceneSlotsGrid.innerHTML = '';

    for (let i = 0; i < TOTAL_SLOTS; i++) {
        const file = sceneSlots[i];
        const slotEl = document.createElement('div');
        slotEl.className = `scene-slot ${file ? 'slot-filled' : 'slot-empty-state'}`;
        slotEl.dataset.slotIndex = i;

        // Top bar badges
        const topBar = document.createElement('div');
        topBar.className = 'slot-top-bar';

        const orderBadge = document.createElement('div');
        orderBadge.className = `slot-badge-order ${i === 0 ? 'scene-flow' : ''}`;
        orderBadge.innerHTML = `<span>Кадр ${i + 1}</span>`;

        topBar.appendChild(orderBadge);

        if (file) {
            const formatTag = document.createElement('div');
            const isVideo = file.type.startsWith('video/');
            formatTag.className = `slot-format-tag ${isVideo ? 'format-mp4' : 'format-photo'}`;
            formatTag.textContent = isVideo ? 'MP4 FLOW' : 'IMAGE';
            topBar.appendChild(formatTag);
        } else if (i === 0) {
            const formatTag = document.createElement('div');
            formatTag.className = 'slot-format-tag format-mp4';
            formatTag.textContent = 'FLOW MP4 / ФОТО';
            topBar.appendChild(formatTag);
        }

        slotEl.appendChild(topBar);

        if (file) {
            // Filled slot view with preview and actions
            const previewWrap = document.createElement('div');
            previewWrap.className = 'slot-preview';
            previewWrap.draggable = true;

            const fileUrl = URL.createObjectURL(file);
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = fileUrl;
                img.alt = `Кадр ${i + 1}`;
                previewWrap.appendChild(img);
            } else {
                const vid = document.createElement('video');
                vid.src = fileUrl;
                vid.muted = true;
                vid.loop = true;
                vid.playsInline = true;
                vid.autoplay = true;
                previewWrap.appendChild(vid);
            }

            // Hover Action Overlay
            const overlay = document.createElement('div');
            overlay.className = 'slot-actions-overlay';

            const info = document.createElement('div');
            info.className = 'slot-media-info';
            info.textContent = file.name;
            overlay.appendChild(info);

            const btnGroup = document.createElement('div');
            btnGroup.className = 'slot-btn-group';

            const replaceBtn = document.createElement('button');
            replaceBtn.type = 'button';
            replaceBtn.className = 'slot-btn';
            replaceBtn.innerHTML = '🔄 Заменить';
            replaceBtn.onclick = (e) => {
                e.stopPropagation();
                triggerSlotReplace(i);
            };

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'slot-btn danger-btn';
            deleteBtn.innerHTML = '🗑️ Удалить';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteSlot(i);
            };

            btnGroup.appendChild(replaceBtn);
            btnGroup.appendChild(deleteBtn);
            overlay.appendChild(btnGroup);
            previewWrap.appendChild(overlay);

            // Drag and drop to reorder
            previewWrap.ondragstart = (e) => {
                slotEl.classList.add('is-dragging');
                e.dataTransfer.setData('text/plain', i.toString());
                e.dataTransfer.effectAllowed = 'move';
            };
            previewWrap.ondragend = () => {
                slotEl.classList.remove('is-dragging');
            };

            slotEl.appendChild(previewWrap);
        } else {
            // Empty slot view
            const emptyWrap = document.createElement('div');
            emptyWrap.className = 'slot-empty';
            emptyWrap.onclick = () => triggerSlotReplace(i);

            let emptyHint = 'Перетащите фото';
            if (i === 0) {
                emptyHint = 'Перетащите MP4 Flow или фото';
            }

            emptyWrap.innerHTML = `
                <div class="slot-empty-icon">${i === 0 ? '🎬' : '🖼️'}</div>
                <div class="slot-empty-title">Кадр ${i + 1}</div>
                <div class="slot-empty-hint">${emptyHint}</div>
                ${i === 0 ? '<div class="slot-empty-badge-flow">Поддерживает MP4 Flow</div>' : ''}
            `;
            slotEl.appendChild(emptyWrap);
        }

        // Slot Drag & Drop handlers (accepts files or reorder swaps)
        slotEl.ondragover = (e) => {
            e.preventDefault();
            slotEl.classList.add('drag-over');
        };
        slotEl.ondragleave = () => {
            slotEl.classList.remove('drag-over');
        };
        slotEl.ondrop = (e) => {
            e.preventDefault();
            slotEl.classList.remove('drag-over');

            // 1. Check if external files were dropped
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const droppedFiles = Array.from(e.dataTransfer.files).filter(f =>
                    f.type.startsWith('image/') || f.type.startsWith('video/')
                );
                if (droppedFiles.length === 1) {
                    assignFileToSlot(droppedFiles[0], i);
                } else if (droppedFiles.length > 1) {
                    assignMultipleFiles(droppedFiles, i);
                }
                return;
            }

            // 2. Otherwise handle reorder swap
            const fromIndexStr = e.dataTransfer.getData('text/plain');
            if (fromIndexStr !== '') {
                const fromIdx = parseInt(fromIndexStr, 10);
                if (!isNaN(fromIdx) && fromIdx !== i) {
                    // Swap slots
                    const temp = sceneSlots[fromIdx];
                    sceneSlots[fromIdx] = sceneSlots[i];
                    sceneSlots[i] = temp;
                    renderSlots();
                    showToast(`Порядок изменен: Кадр ${fromIdx + 1} ⇄ Кадр ${i + 1}`, 'info', 2500);
                }
            }
        };

        sceneSlotsGrid.appendChild(slotEl);
    }
}

function assignFileToSlot(file, slotIndex) {
    if (slotIndex < 0 || slotIndex >= TOTAL_SLOTS) return;
    if (slotIndex > 0 && file.type.startsWith('video/')) {
        showToast(`Внимание: Видео MP4 (Flow) рекомендуется использовать только для Кадра 1. Кадр ${slotIndex + 1} ожидает фото.`, 'warning', 4500);
    }
    sceneSlots[slotIndex] = file;
    renderSlots();
    showToast(`✓ Кадр ${slotIndex + 1} обновлен: ${file.name}`, 'success', 2500);
}

function assignMultipleFiles(files, startingSlot = 0) {
    const valid = files.filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    if (valid.length === 0) {
        showToast('Не выбрано ни одного поддерживаемого файла (фото или видео)', 'error');
        return;
    }

    let assignedCount = 0;
    for (let i = 0; i < valid.length && (startingSlot + i) < TOTAL_SLOTS; i++) {
        sceneSlots[startingSlot + i] = valid[i];
        assignedCount++;
    }
    renderSlots();
    showToast(`Загружено ${assignedCount} кадров в таймлайн`, 'success');
}

function deleteSlot(slotIndex) {
    if (slotIndex >= 0 && slotIndex < TOTAL_SLOTS) {
        const deletedFile = sceneSlots[slotIndex];
        sceneSlots[slotIndex] = null;
        renderSlots();
        if (deletedFile) {
            showToast(`Кадр ${slotIndex + 1} удален`, 'info', 2000);
        }
    }
}

function clearAllSlots() {
    sceneSlots = new Array(TOTAL_SLOTS).fill(null);
    renderSlots();
    showToast('Все 5 кадров очищены', 'info', 2000);
}

function triggerSlotReplace(slotIndex) {
    targetReplaceSlotIndex = slotIndex;
    if (slotReplaceInput) {
        slotReplaceInput.value = '';
        slotReplaceInput.click();
    }
}

function setupDropzoneListeners() {
    if (dropzone && fileInput) {
        dropzone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            if (e.target.files && e.target.files.length > 0) {
                assignMultipleFiles(Array.from(e.target.files), 0);
            }
        };

        dropzone.ondragover = (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        };
        dropzone.ondragleave = () => {
            dropzone.classList.remove('dragover');
        };
        dropzone.ondrop = (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                assignMultipleFiles(Array.from(e.dataTransfer.files), 0);
            }
        };
    }

    if (slotReplaceInput) {
        slotReplaceInput.onchange = (e) => {
            if (e.target.files && e.target.files.length > 0 && targetReplaceSlotIndex !== null) {
                assignFileToSlot(e.target.files[0], targetReplaceSlotIndex);
                targetReplaceSlotIndex = null;
            }
        };
    }

    if (bulkUploadBtn && fileInput) {
        bulkUploadBtn.onclick = () => fileInput.click();
    }

    if (clearAllSlotsBtn) {
        clearAllSlotsBtn.onclick = clearAllSlots;
    }
}

function setupAudioInputListener() {
    if (customAudioInput && customAudioPlaceholder) {
        customAudioInput.onchange = (e) => {
            if (e.target.files && e.target.files.length > 0) {
                customAudioPlaceholder.textContent = `Выбрано: ${e.target.files[0].name}`;
                customAudioPlaceholder.style.color = 'var(--text-primary)';
                showToast(`Аудиодорожка выбрана: ${e.target.files[0].name}`, 'info');
            } else {
                customAudioPlaceholder.textContent = 'Выберите MP3 / WAV (или оставьте Дмитрия)';
                customAudioPlaceholder.style.color = 'var(--text-muted)';
            }
        };
    }
}

// ==============================================================================
// 4. MULTI-STEP PROGRESS & RENDER PIPELINE
// ==============================================================================
function setProgressStep(stepNum, percent) {
    const fill = document.getElementById('progressFill');
    const percentEl = document.getElementById('progressPercentage');
    if (fill) fill.style.width = `${percent}%`;
    if (percentEl) percentEl.textContent = `${percent}%`;

    const s1 = document.getElementById('step1Indicator');
    const s2 = document.getElementById('step2Indicator');
    const s3 = document.getElementById('step3Indicator');

    [s1, s2, s3].forEach((el, idx) => {
        if (!el) return;
        const currentStep = idx + 1;
        el.classList.remove('active', 'completed');
        if (currentStep < stepNum) {
            el.classList.add('completed');
            el.querySelector('.step-dot').innerHTML = '✓';
        } else if (currentStep === stepNum) {
            el.classList.add('active');
            el.querySelector('.step-dot').innerHTML = currentStep;
        } else {
            el.querySelector('.step-dot').innerHTML = currentStep;
        }
    });
}

function startProgressAnimation() {
    let currentStep = 1;
    let percent = 5;
    setProgressStep(currentStep, percent);

    if (progressInterval) clearInterval(progressInterval);

    // Realistic progression simulation while backend processes video
    progressInterval = setInterval(() => {
        if (currentStep === 1) {
            // Voice synthesis step
            if (percent < 33) {
                percent += Math.floor(Math.random() * 4) + 2;
                setProgressStep(1, Math.min(percent, 33));
            } else {
                currentStep = 2;
                percent = 35;
                setProgressStep(2, percent);
            }
        } else if (currentStep === 2) {
            // Frame processing & crossfades
            if (percent < 70) {
                percent += Math.floor(Math.random() * 3) + 1;
                setProgressStep(2, Math.min(percent, 70));
            } else {
                currentStep = 3;
                percent = 72;
                setProgressStep(3, percent);
            }
        } else if (currentStep === 3) {
            // Final render & encoding
            if (percent < 96) {
                percent += 1;
                setProgressStep(3, Math.min(percent, 96));
            }
        }
    }, 450);
}

function stopProgressAnimation(isSuccess) {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    if (isSuccess) {
        setProgressStep(3, 100);
        const s3 = document.getElementById('step3Indicator');
        if (s3) {
            s3.classList.remove('active');
            s3.classList.add('completed');
            s3.querySelector('.step-dot').innerHTML = '✓';
        }
    }
}

// ==============================================================================
// 5. START GENERATION (BACKEND CALL)
// ==============================================================================
async function startGeneration() {
    // Validate that all 5 scene slots are filled
    const missingSlots = [];
    for (let i = 0; i < TOTAL_SLOTS; i++) {
        if (!sceneSlots[i]) missingSlots.push(i + 1);
    }

    if (missingSlots.length > 0) {
        showToast(`Необходимо загрузить все 5 сцен для монтажа! Отсутствуют кадры: ${missingSlots.join(', ')}`, 'warning', 5000);
        return;
    }

    const dishNameVal = document.getElementById('dishName')?.value.trim() || 'Рецепт';
    const voiceTextVal = document.getElementById('voiceText')?.value.trim() || '';

    if (!voiceTextVal) {
        showToast('Введите текст диктора Дмитрия!', 'warning');
        return;
    }

    const btn = document.getElementById('generateBtn');
    const statusBox = document.getElementById('statusBox');
    const resultCard = document.getElementById('resultCard');

    btn.disabled = true;
    statusBox.style.display = 'block';
    resultCard.style.display = 'none';

    startProgressAnimation();

    const formData = new FormData();
    formData.append('dish_name', dishNameVal);
    formData.append('voice_text', voiceTextVal);
    formData.append('post_kit', document.getElementById('fullPostKit')?.value || '');

    const subs = [
        document.getElementById('sub0')?.value || '',
        document.getElementById('sub1')?.value || '',
        document.getElementById('sub2')?.value || '',
        document.getElementById('sub3')?.value || '',
        document.getElementById('sub4')?.value || ''
    ];
    formData.append('subtitles', JSON.stringify(subs));

    const customAudio = customAudioInput?.files[0];
    if (customAudio) {
        formData.append('custom_audio', customAudio);
    }

    // Append media files in exact slot order 0..4
    sceneSlots.forEach((file, idx) => {
        formData.append('media_files', file, `file_${idx}_${file.name}`);
    });

    try {
        const response = await fetch('/render_reel', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.status === 'ok') {
            stopProgressAnimation(true);

            const player = document.getElementById('resultPlayer');
            const link = document.getElementById('downloadLink');
            const postLink = document.getElementById('downloadPostKit');

            player.src = data.video_url + '?t=' + new Date().getTime();
            link.href = data.video_url;
            postLink.href = data.post_kit_url;

            // Smooth reveal of result
            setTimeout(() => {
                statusBox.style.display = 'none';
                resultCard.style.display = 'block';
                resultCard.scrollIntoView({ behavior: 'smooth' });
                showToast('🎉 Вертикальный Reel успешно смонтирован!', 'success', 5000);
            }, 600);
        } else {
            stopProgressAnimation(false);
            statusBox.style.display = 'none';
            showToast('Ошибка монтажа: ' + (data.message || 'Неизвестная ошибка'), 'error', 6000);
        }
    } catch (err) {
        stopProgressAnimation(false);
        statusBox.style.display = 'none';
        showToast('Сбой связи с сервером: ' + err.message, 'error', 6000);
    } finally {
        btn.disabled = false;
    }
}

// Global initialization
document.addEventListener('DOMContentLoaded', initSlots);
