/**
 * SessionsManager — клиент для работы с API сессий
 */
class SessionsManager {
    constructor() {
        this.apiUrl = window.API_URL || '/api';
        this.telegram = window.Telegram?.WebApp;
    }

    /**
     * Получить заголовки для запроса с аутентификацией
     */
    _getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.telegram?.initData) {
            headers['X-Telegram-Init-Data'] = this.telegram.initData;
        }
        return headers;
    }

    /**
     * Выполнить API запрос с обработкой ошибок
     */
    async _fetch(url, options = {}) {
        try {
            const response = await fetch(`${this.apiUrl}${url}`, {
                ...options,
                headers: this._getHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error (${url}):`, error);
            throw error;
        }
    }

    /**
     * Получить список сессий
     * @param {string|null} status - Фильтр по статусу
     * @param {number} limit - Максимальное количество
     */
    async getSessions(status = null, limit = 50) {
        let url = `/sessions?limit=${limit}`;
        if (status) {
            url += `&status=${status}`;
        }
        return this._fetch(url);
    }

    /**
     * Получить детали сессии
     * @param {number} sessionId - ID сессии
     */
    async getSession(sessionId) {
        return this._fetch(`/sessions/${sessionId}`);
    }

    /**
     * Получить сообщения сессии
     * @param {number} sessionId - ID сессии
     * @param {number|null} limit - Лимит сообщений
     */
    async getSessionMessages(sessionId, limit = null) {
        let url = `/sessions/${sessionId}/messages`;
        if (limit) {
            url += `?limit=${limit}`;
        }
        return this._fetch(url);
    }

    /**
     * Переключиться на сессию
     * @param {number} sessionId - ID сессии
     */
    async switchSession(sessionId) {
        return this._fetch(`/sessions/${sessionId}/switch`, {
            method: 'POST'
        });
    }

    /**
     * Завершить сессию
     * @param {number} sessionId - ID сессии
     */
    async endSession(sessionId) {
        return this._fetch(`/sessions/${sessionId}/end`, {
            method: 'POST'
        });
    }

    /**
     * Удалить сессию
     * @param {number} sessionId - ID сессии
     */
    async deleteSession(sessionId) {
        return this._fetch(`/sessions/${sessionId}/delete`, {
            method: 'POST'
        });
    }

    /**
     * Поиск сессий
     * @param {string} query - Поисковый запрос
     */
    async searchSessions(query) {
        return this._fetch(`/sessions/search?q=${encodeURIComponent(query)}`);
    }

    /**
     * Получить содержимое файла
     * @param {string} filePath - Путь к файлу
     */
    async viewFile(filePath) {
        return this._fetch(`/files/view?path=${encodeURIComponent(filePath)}`);
    }

    /**
     * Получить список файлов в директории
     * @param {string} dirPath - Путь к директории
     */
    async listFiles(dirPath = '') {
        return this._fetch(`/files/list?path=${encodeURIComponent(dirPath)}`);
    }
}

