#!/usr/bin/env bash
# After danilpdr registers/logs in on prod: set host isolation, kb_folder, admin,
# and reassign legacy sessions/devices from telegram user id=1.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:${PATH}"

docker exec knowledge-base-bot-db psql -U postgres -d knowledge_base_bot <<'SQL'
UPDATE users
SET cursor_isolation = 'host',
    kb_folder = '/KnowledgeBase',
    nextcloud_username = COALESCE(NULLIF(nextcloud_username, ''), 'danilpdr'),
    vault_root_relative = COALESCE(NULLIF(vault_root_relative, ''), 'users/danilpdr'),
    is_admin = true,
    is_allowed = true,
    role = 'admin'
WHERE lower(login) = 'danilpdr';

UPDATE sessions
SET user_id = (SELECT id FROM users WHERE lower(login) = 'danilpdr')
WHERE user_id = 1
  AND EXISTS (SELECT 1 FROM users WHERE lower(login) = 'danilpdr');

UPDATE user_devices
SET user_id = (SELECT id FROM users WHERE lower(login) = 'danilpdr')
WHERE user_id = 1
  AND EXISTS (SELECT 1 FROM users WHERE lower(login) = 'danilpdr');

SELECT id, login, role, cursor_isolation, kb_folder, vault_root_relative,
       is_admin, is_allowed,
       (nc_app_password_enc IS NOT NULL) AS has_nc
FROM users WHERE lower(login) = 'danilpdr';

SELECT user_id, COUNT(*) FROM sessions GROUP BY user_id ORDER BY 2 DESC;
SQL
