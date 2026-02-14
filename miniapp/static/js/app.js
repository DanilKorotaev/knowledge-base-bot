/**
 * Mini App — главное приложение
 */
(function() {
    'use strict';

    // ========================================
    // Инициализация
    // ========================================

    const tg = window.Telegram?.WebApp;
    const api = new SessionsManager();

    // Состояние приложения
    const state = {
        currentScreen: 'loading',
        sessions: [],
        activeSessionId: null,
        currentSessionId: null,
        currentFilter: 'all',
        currentFilePath: '',
        previousScreen: null
    };

    // Элементы DOM
    const screens = {
        loading: document.getElementById('loading-screen'),
        sessions: document.getElementById('sessions-screen'),
        sessionDetail: document.getElementById('session-detail-screen'),
        fileView: document.getElementById('file-view-screen'),
        filesBrowser: document.getElementById('files-browser-screen')
    };

    // ========================================
    // Навигация между экранами
    // ========================================

    function showScreen(name) {
        // Скрыть все экраны
        Object.values(screens).forEach(s => s.classList.remove('active'));
        
        // Показать нужный экран
        if (screens[name]) {
            screens[name].classList.add('active');
            state.previousScreen = state.currentScreen;
            state.currentScreen = name;
        }
    }

    // ========================================
    // Toast уведомления
    // ========================================

    function showToast(message, type = '') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    // ========================================
    // Модальное окно подтверждения
    // ========================================

    function showConfirm(text) {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirm-modal');
            const confirmText = document.getElementById('confirm-text');
            const yesBtn = document.getElementById('confirm-yes');
            const noBtn = document.getElementById('confirm-no');
            const overlay = modal.querySelector('.modal-overlay');

            confirmText.textContent = text;
            modal.classList.remove('hidden');

            const cleanup = () => {
                modal.classList.add('hidden');
                yesBtn.removeEventListener('click', onYes);
                noBtn.removeEventListener('click', onNo);
                overlay.removeEventListener('click', onNo);
            };

            const onYes = () => { cleanup(); resolve(true); };
            const onNo = () => { cleanup(); resolve(false); };

            yesBtn.addEventListener('click', onYes);
            noBtn.addEventListener('click', onNo);
            overlay.addEventListener('click', onNo);
        });
    }

    // ========================================
    // Форматирование
    // ========================================

    function formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            
            const now = new Date();
            const isToday = d.toDateString() === now.toDateString();
            
            const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            
            if (isToday) {
                return `Сегодня, ${time}`;
            }
            
            return d.toLocaleDateString('ru-RU', {
                day: 'numeric',
                month: 'short',
                year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
            }) + `, ${time}`;
        } catch {
            return dateStr;
        }
    }

    function formatSessionType(type) {
        return type === 'query_with_kb'
            ? { emoji: '📚', label: 'С контекстом БЗ' }
            : { emoji: '💬', label: 'Без контекста' };
    }

    function formatStatus(status) {
        const map = {
            active: { emoji: '🟢', label: 'Активна', class: 'active' },
            completed: { emoji: '⚪', label: 'Завершена', class: 'completed' },
            deleted: { emoji: '🗑', label: 'Удалена', class: 'completed' }
        };
        return map[status] || { emoji: '⚪', label: status, class: 'completed' };
    }

    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(text || '');
            } catch {
                return escapeHtml(text || '');
            }
        }
        return escapeHtml(text || '');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatFileSize(bytes) {
        if (bytes == null) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    // ========================================
    // Рендеринг вложений
    // ========================================

    function renderAttachments(attachments) {
        if (!attachments || attachments.length === 0) return '';

        const items = attachments.map(att => {
            const type = att.file_type;
            const name = att.file_name || `file_${att.id}`;
            const size = formatFileSize(att.file_size);

            if (type === 'photo') {
                return `
                    <div class="attachment attachment-photo" data-attachment-id="${att.id}">
                        <div class="attachment-photo-placeholder">🖼️ Загрузка...</div>
                    </div>
                `;
            }

            if (type === 'voice') {
                return `
                    <div class="attachment attachment-voice" data-attachment-id="${att.id}">
                        <span class="attachment-icon">🎤</span>
                        <span class="attachment-label">Голосовое сообщение</span>
                        <audio class="attachment-audio" controls preload="none"></audio>
                    </div>
                `;
            }

            if (type === 'audio') {
                return `
                    <div class="attachment attachment-audio-file" data-attachment-id="${att.id}">
                        <span class="attachment-icon">🎵</span>
                        <span class="attachment-label">${escapeHtml(name)}</span>
                        ${size ? `<span class="attachment-size">${size}</span>` : ''}
                    </div>
                `;
            }

            if (type === 'video') {
                return `
                    <div class="attachment attachment-video" data-attachment-id="${att.id}">
                        <span class="attachment-icon">🎬</span>
                        <span class="attachment-label">${escapeHtml(name)}</span>
                        ${size ? `<span class="attachment-size">${size}</span>` : ''}
                    </div>
                `;
            }

            // document и прочие
            const icon = getFileIcon(name);
            return `
                <div class="attachment attachment-document" data-attachment-id="${att.id}">
                    <span class="attachment-icon">${icon}</span>
                    <span class="attachment-label">${escapeHtml(name)}</span>
                    ${size ? `<span class="attachment-size">${size}</span>` : ''}
                </div>
            `;
        }).join('');

        return `<div class="attachments-list">${items}</div>`;
    }

    async function loadAttachmentImages() {
        // Загружаем фото через blob URL
        const photoEls = document.querySelectorAll('.attachment-photo[data-attachment-id]');
        for (const el of photoEls) {
            const attId = el.dataset.attachmentId;
            try {
                const blobUrl = await api.getAttachmentBlobUrl(attId);
                el.innerHTML = `<img src="${blobUrl}" class="attachment-img" alt="Фото" onclick="window.open('${blobUrl}', '_blank')">`;
            } catch {
                el.innerHTML = `<div class="attachment-photo-placeholder">🖼️ Не удалось загрузить</div>`;
            }
        }

        // Загружаем аудио для голосовых
        const voiceEls = document.querySelectorAll('.attachment-voice[data-attachment-id]');
        for (const el of voiceEls) {
            const attId = el.dataset.attachmentId;
            const audioEl = el.querySelector('audio');
            if (audioEl) {
                try {
                    const blobUrl = await api.getAttachmentBlobUrl(attId);
                    audioEl.src = blobUrl;
                } catch {
                    el.querySelector('.attachment-label').textContent = 'Аудио недоступно';
                }
            }
        }
    }

    // ========================================
    // Загрузка и отображение сессий
    // ========================================

    async function loadSessions() {
        try {
            const statusFilter = state.currentFilter === 'all' ? null : state.currentFilter;
            const data = await api.getSessions(statusFilter);
            
            state.sessions = data.sessions || [];
            state.activeSessionId = data.active_session_id;
            
            renderSessions();
            showScreen('sessions');
        } catch (error) {
            showToast('Ошибка загрузки сессий: ' + error.message, 'error');
            showScreen('sessions');
            renderSessions();
        }
    }

    function renderSessions() {
        const list = document.getElementById('sessions-list');
        const empty = document.getElementById('sessions-empty');

        if (!state.sessions.length) {
            list.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }

        empty.classList.add('hidden');

        list.innerHTML = state.sessions.map(session => {
            const type = formatSessionType(session.session_type);
            const status = formatStatus(session.status);
            const isActive = session.id === state.activeSessionId;

            return `
                <div class="session-card ${isActive ? 'active' : ''}" data-session-id="${session.id}">
                    <div class="session-card-header">
                        <span class="session-id">${type.emoji} #${session.id}</span>
                        <span class="session-status ${status.class}">${status.emoji} ${status.label}</span>
                    </div>
                    <div class="session-card-body">
                        <span class="session-type">${type.label}</span>
                        <span class="session-messages-count">💬 ${session.messages_count || 0}</span>
                        <span class="session-date">${formatDate(session.created_at)}</span>
                    </div>
                </div>
            `;
        }).join('');

        // Привязать клики
        list.querySelectorAll('.session-card').forEach(card => {
            card.addEventListener('click', () => {
                const sessionId = parseInt(card.dataset.sessionId);
                openSessionDetail(sessionId);
            });
        });
    }

    // ========================================
    // Детали сессии
    // ========================================

    async function openSessionDetail(sessionId) {
        state.currentSessionId = sessionId;
        showScreen('sessionDetail');

        // Показать скелетон загрузки
        const messagesList = document.getElementById('messages-list');
        messagesList.innerHTML = Array(4).fill(0).map((_, i) =>
            `<div class="skeleton skeleton-message" style="width: ${i % 2 === 0 ? '70%' : '60%'}; align-self: ${i % 2 === 0 ? 'flex-start' : 'flex-end'}"></div>`
        ).join('');

        try {
            // Загрузить данные параллельно
            const [sessionData, messagesData] = await Promise.all([
                api.getSession(sessionId),
                api.getSessionMessages(sessionId)
            ]);

            renderSessionDetail(sessionData, messagesData.messages || []);
        } catch (error) {
            showToast('Ошибка загрузки сессии: ' + error.message, 'error');
        }
    }

    function renderSessionDetail(session, messages) {
        const title = document.getElementById('session-title');
        const info = document.getElementById('session-info');
        const messagesList = document.getElementById('messages-list');
        const actions = document.getElementById('session-actions');

        const type = formatSessionType(session.session_type);
        const status = formatStatus(session.status);
        const isActive = session.is_active;

        // Компактный заголовок
        title.textContent = `${type.emoji} #${session.id}`;

        // Информация о сессии (для модального окна)
        info.innerHTML = `
            <div class="session-info-row">
                <span class="session-info-label">Статус</span>
                <span class="session-info-value">${status.emoji} ${status.label}</span>
            </div>
            <div class="session-info-row">
                <span class="session-info-label">Тип</span>
                <span class="session-info-value">${type.label}</span>
            </div>
            <div class="session-info-row">
                <span class="session-info-label">Сообщений</span>
                <span class="session-info-value">${messages.length}</span>
            </div>
            <div class="session-info-row">
                <span class="session-info-label">Создана</span>
                <span class="session-info-value">${formatDate(session.created_at)}</span>
            </div>
        `;

        // Сообщения
        if (messages.length === 0) {
            messagesList.innerHTML = `
                <div class="empty-state" style="min-height: 20vh;">
                    <p class="hint">Нет сообщений в этой сессии</p>
                </div>
            `;
        } else {
            messagesList.innerHTML = messages.map(msg => {
                const isUser = msg.role === 'user';
                const roleLabel = isUser ? '👤 Вы' : '🤖 Ассистент';
                const content = isUser ? escapeHtml(msg.content) : renderMarkdown(msg.content);
                const attachmentsHtml = renderAttachments(msg.attachments || []);

                return `
                    <div class="message ${isUser ? 'user' : 'assistant'}">
                        <div class="message-role">${roleLabel}</div>
                        ${attachmentsHtml}
                        <div class="message-content">${content}</div>
                        <div class="message-time">${formatDate(msg.created_at)}</div>
                    </div>
                `;
            }).join('');

            // Загрузить фото вложений (blob URLs)
            loadAttachmentImages();

            // Прокрутка к последнему сообщению
            requestAnimationFrame(() => {
                messagesList.scrollTop = messagesList.scrollHeight;
            });
        }

        // Действия (для bottom sheet)
        let actionsHtml = '';

        if (!isActive && session.status !== 'deleted') {
            actionsHtml += `<button class="action-item" id="btn-switch"><span class="action-icon">🔄</span><span>Переключиться на эту сессию</span></button>`;
        }

        if (isActive) {
            actionsHtml += `<button class="action-item" id="btn-end"><span class="action-icon">⏹</span><span>Завершить сессию</span></button>`;
        }

        if (session.status !== 'deleted') {
            actionsHtml += `<button class="action-item danger" id="btn-delete"><span class="action-icon">🗑</span><span>Удалить сессию</span></button>`;
        }

        actionsHtml += `<button class="action-item" id="btn-close-miniapp"><span class="action-icon">💬</span><span>Вернуться в чат</span></button>`;

        actions.innerHTML = actionsHtml;

        // Привязать действия (закрывают sheet перед выполнением)
        const closeSheet = () => {
            document.getElementById('session-actions-sheet').classList.add('hidden');
        };

        const switchBtn = document.getElementById('btn-switch');
        const endBtn = document.getElementById('btn-end');
        const deleteBtn = document.getElementById('btn-delete');
        const closeBtn = document.getElementById('btn-close-miniapp');

        if (switchBtn) {
            switchBtn.addEventListener('click', () => { closeSheet(); handleSwitchSession(session.id); });
        }
        if (endBtn) {
            endBtn.addEventListener('click', () => { closeSheet(); handleEndSession(session.id); });
        }
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => { closeSheet(); handleDeleteSession(session.id); });
        }
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                closeSheet();
                if (tg) tg.close();
            });
        }
    }

    // ========================================
    // Действия с сессиями
    // ========================================

    async function handleSwitchSession(sessionId) {
        try {
            await api.switchSession(sessionId);
            showToast('✅ Сессия переключена', 'success');
            
            // Обновить состояние
            state.activeSessionId = sessionId;
            
            // Закрыть Mini App (вернуться в чат)
            if (tg) {
                tg.close();
            } else {
                // Для разработки: обновить экран
                await loadSessions();
                showScreen('sessions');
            }
        } catch (error) {
            showToast('Ошибка: ' + error.message, 'error');
        }
    }

    async function handleEndSession(sessionId) {
        const confirmed = await showConfirm('Завершить эту сессию?');
        if (!confirmed) return;

        try {
            await api.endSession(sessionId);
            showToast('✅ Сессия завершена', 'success');
            
            // Вернуться к списку и обновить
            await loadSessions();
        } catch (error) {
            showToast('Ошибка: ' + error.message, 'error');
        }
    }

    async function handleDeleteSession(sessionId) {
        const confirmed = await showConfirm('Удалить эту сессию? Это действие нельзя отменить.');
        if (!confirmed) return;

        try {
            await api.deleteSession(sessionId);
            showToast('✅ Сессия удалена', 'success');
            
            // Вернуться к списку и обновить
            await loadSessions();
        } catch (error) {
            showToast('Ошибка: ' + error.message, 'error');
        }
    }

    // ========================================
    // Просмотр файлов
    // ========================================

    async function openFile(filePath) {
        showScreen('fileView');
        
        const title = document.getElementById('file-title');
        const content = document.getElementById('file-content');
        
        title.textContent = filePath.split('/').pop() || filePath;
        content.innerHTML = '<div class="skeleton" style="height: 200px;"></div>';

        try {
            const data = await api.viewFile(filePath);
            content.innerHTML = renderMarkdown(data.content);
        } catch (error) {
            content.innerHTML = `<div class="empty-state"><p class="hint">Ошибка загрузки файла: ${escapeHtml(error.message)}</p></div>`;
        }
    }

    async function openFileBrowser(dirPath = '') {
        state.currentFilePath = dirPath;
        showScreen('filesBrowser');

        const title = document.getElementById('files-title');
        const breadcrumb = document.getElementById('files-breadcrumb');
        const list = document.getElementById('files-list');

        title.textContent = dirPath ? `📁 ${dirPath.split('/').pop()}` : '📁 Файлы базы знаний';
        
        // Хлебные крошки
        const parts = dirPath ? dirPath.split('/') : [];
        let breadcrumbHtml = `<span class="breadcrumb-item" data-path="">🏠 Корень</span>`;
        let currentPath = '';
        for (const part of parts) {
            currentPath += (currentPath ? '/' : '') + part;
            breadcrumbHtml += `<span class="breadcrumb-separator"> / </span>`;
            breadcrumbHtml += `<span class="breadcrumb-item" data-path="${escapeHtml(currentPath)}">${escapeHtml(part)}</span>`;
        }
        breadcrumb.innerHTML = breadcrumbHtml;

        // Привязать клики на хлебные крошки
        breadcrumb.querySelectorAll('.breadcrumb-item').forEach(item => {
            item.addEventListener('click', () => {
                openFileBrowser(item.dataset.path);
            });
        });

        // Загрузить файлы
        list.innerHTML = Array(5).fill(0).map(() =>
            '<div class="skeleton" style="height: 48px; margin-bottom: 4px;"></div>'
        ).join('');

        try {
            const data = await api.listFiles(dirPath);
            
            if (!data.items || data.items.length === 0) {
                list.innerHTML = '<div class="empty-state" style="min-height: 20vh;"><p class="hint">Папка пуста</p></div>';
                return;
            }

            list.innerHTML = data.items.map(item => {
                const icon = item.is_dir ? '📁' : getFileIcon(item.name);
                const size = item.is_dir ? '' : formatFileSize(item.size);

                return `
                    <div class="file-item" data-path="${escapeHtml(item.path)}" data-is-dir="${item.is_dir}">
                        <span class="file-icon">${icon}</span>
                        <span class="file-name">${escapeHtml(item.name)}</span>
                        ${size ? `<span class="file-size">${size}</span>` : ''}
                    </div>
                `;
            }).join('');

            // Привязать клики
            list.querySelectorAll('.file-item').forEach(item => {
                item.addEventListener('click', () => {
                    const path = item.dataset.path;
                    const isDir = item.dataset.isDir === 'true';
                    if (isDir) {
                        openFileBrowser(path);
                    } else {
                        openFile(path);
                    }
                });
            });
        } catch (error) {
            list.innerHTML = `<div class="empty-state" style="min-height: 20vh;"><p class="hint">Ошибка: ${escapeHtml(error.message)}</p></div>`;
        }
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop()?.toLowerCase();
        const icons = {
            md: '📝', txt: '📄', pdf: '📕',
            png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', webp: '🖼️',
            py: '🐍', js: '📜', ts: '📜', html: '🌐', css: '🎨',
            json: '📋', yml: '📋', yaml: '📋', xml: '📋',
            zip: '📦', tar: '📦', gz: '📦',
            mp3: '🎵', wav: '🎵', ogg: '🎵',
            mp4: '🎬', avi: '🎬', mkv: '🎬'
        };
        return icons[ext] || '📄';
    }

    // ========================================
    // Привязка событий
    // ========================================

    // Debounce utility
    function debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    }

    // Search handler
    async function handleSearch(query) {
        if (!query.trim()) {
            await loadSessions();
            return;
        }

        try {
            const data = await api.searchSessions(query.trim());
            state.sessions = data.sessions || [];
            state.activeSessionId = data.active_session_id || state.activeSessionId;
            renderSessions();
        } catch (error) {
            showToast('Ошибка поиска: ' + error.message, 'error');
        }
    }

    const debouncedSearch = debounce(handleSearch, 400);

    // ========================================
    // Вспомогательные функции для модалов/шитов
    // ========================================

    function closeAllOverlays() {
        document.getElementById('session-info-modal').classList.add('hidden');
        document.getElementById('session-actions-sheet').classList.add('hidden');
    }

    function bindEvents() {
        // Поиск
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                debouncedSearch(e.target.value);
            });
        }

        // Фильтры
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.currentFilter = btn.dataset.filter;
                // Сбросить поиск при смене фильтра
                if (searchInput) searchInput.value = '';
                loadSessions();
            });
        });

        // Кнопка "Назад" к списку сессий
        document.getElementById('back-to-sessions').addEventListener('click', () => {
            closeAllOverlays();
            loadSessions();
        });

        // Кнопка ℹ️ — показать информацию о сессии
        document.getElementById('btn-session-info').addEventListener('click', () => {
            document.getElementById('session-info-modal').classList.remove('hidden');
        });

        // Закрыть модалку информации
        document.getElementById('session-info-close').addEventListener('click', () => {
            document.getElementById('session-info-modal').classList.add('hidden');
        });
        document.querySelector('#session-info-modal .modal-overlay').addEventListener('click', () => {
            document.getElementById('session-info-modal').classList.add('hidden');
        });

        // Кнопка ⋮ — показать меню действий
        document.getElementById('btn-session-menu').addEventListener('click', () => {
            document.getElementById('session-actions-sheet').classList.remove('hidden');
        });

        // Закрыть bottom sheet по overlay
        document.querySelector('#session-actions-sheet .bottom-sheet-overlay').addEventListener('click', () => {
            document.getElementById('session-actions-sheet').classList.add('hidden');
        });

        // Кнопка "Назад" из просмотра файла
        document.getElementById('back-from-file').addEventListener('click', () => {
            if (state.previousScreen === 'filesBrowser') {
                openFileBrowser(state.currentFilePath);
            } else if (state.previousScreen === 'sessionDetail') {
                showScreen('sessionDetail');
            } else {
                loadSessions();
            }
        });

        // Кнопка "Назад" из обозревателя файлов
        document.getElementById('back-from-files').addEventListener('click', () => {
            if (state.currentFilePath) {
                // Подняться на уровень вверх
                const parts = state.currentFilePath.split('/');
                parts.pop();
                openFileBrowser(parts.join('/'));
            } else {
                loadSessions();
            }
        });
    }

    // ========================================
    // Инициализация Telegram Web App
    // ========================================

    function initTelegramWebApp() {
        if (!tg) {
            console.log('Telegram WebApp API не доступен — режим разработки');
            return;
        }

        // Раскрыть на полный экран
        tg.expand();

        // Установить цвет хедера
        tg.setHeaderColor('secondary_bg_color');
        tg.setBackgroundColor('bg_color');

        // Обработка кнопки "Назад" в Telegram
        tg.BackButton.onClick(() => {
            closeAllOverlays();
            if (state.currentScreen === 'sessionDetail') {
                loadSessions();
            } else if (state.currentScreen === 'fileView') {
                if (state.previousScreen === 'filesBrowser') {
                    openFileBrowser(state.currentFilePath);
                } else {
                    loadSessions();
                }
            } else if (state.currentScreen === 'filesBrowser') {
                if (state.currentFilePath) {
                    const parts = state.currentFilePath.split('/');
                    parts.pop();
                    openFileBrowser(parts.join('/'));
                } else {
                    loadSessions();
                }
            } else {
                tg.close();
            }
        });

        // Обновляем видимость кнопки "Назад"
        const observer = new MutationObserver(() => {
            if (state.currentScreen !== 'sessions') {
                tg.BackButton.show();
            } else {
                tg.BackButton.hide();
            }
        });

        observer.observe(document.getElementById('app'), {
            childList: true,
            subtree: true
        });
    }

    // ========================================
    // Запуск
    // ========================================

    async function init() {
        initTelegramWebApp();
        bindEvents();
        
        // Загрузить сессии
        await loadSessions();

        // Обновляем кнопку Назад
        if (tg) {
            tg.BackButton.hide();
        }
    }

    // Запуск при загрузке страницы
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Экспортируем для использования в других модулях
    window.MiniApp = {
        openFile,
        openFileBrowser,
        openSessionDetail,
        loadSessions,
        showToast
    };
})();

