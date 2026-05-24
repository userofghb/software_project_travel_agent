USE travel_agent;

-- =========================
-- users
-- =========================

INSERT INTO users (
    id,
    username,
    email,
    password_hash,
    status,
    created_at,
    updated_at
)
VALUES
(
    1,
    'alice',
    'alice@example.com',
    '$pbkdf2-sha256$29000$3puzllLK.R8jxLh3TglhjA$jKE00rAK7Dq.cG1OMRvH7LmnoeE4ma42u76jVido5jo',
    'active',
    NOW(),
    NOW()
),
(
    2,
    'li',
    'li@example.com',
    '$pbkdf2-sha256$29000$3puzllLK.R8jxLh3TglhjA$jKE00rAK7Dq.cG1OMRvH7LmnoeE4ma42u76jVido5jo',
    'active',
    NOW(),
    NOW()
),
(
    3,
    'wang',
    'wang@example.com',
    '$pbkdf2-sha256$29000$3puzllLK.R8jxLh3TglhjA$jKE00rAK7Dq.cG1OMRvH7LmnoeE4ma42u76jVido5jo',
    'disabled',
    NOW(),
    NOW()
);

-- =========================
-- user_profiles
-- =========================

INSERT INTO user_profiles (
    id,
    user_id,
    profile_json,
    profile_summary,
    updated_at
)
VALUES
(
    1,
    1,
    JSON_OBJECT(
        'travel_style', 'relaxed',
        'budget', 'medium',
        'favorite_city', '成都'
    ),
    '喜欢轻松旅行，中等预算，偏好成都。',
    NOW()
),
(
    2,
    2,
    JSON_OBJECT(
        'travel_style', 'adventure',
        'budget', 'high',
        'favorite_city', '西藏'
    ),
    '喜欢冒险旅行，高预算。',
    NOW()
);

-- =========================
-- trip_plans
-- =========================

INSERT INTO trip_plans (
    id,
    owner_user_id,
    title,
    city,
    start_date,
    end_date,
    budget_range,
    current_version_id,
    created_at,
    updated_at
)
VALUES
(
    1,
    1,
    '成都七日游',
    '成都',
    '2026-04-01',
    '2026-04-07',
    'medium',
    NULL,
    NOW(),
    NOW()
),
(
    2,
    2,
    '西藏五日游',
    '西藏',
    '2026-05-10',
    '2026-05-15',
    'high',
    NULL,
    NOW(),
    NOW()
);

-- =========================
-- trip_plan_version
-- =========================

INSERT INTO trip_plan_versions (
    id,
    plan_id,
    parent_version_id,
    owner_user_id,
    version_no,
    source_type,
    change_summary,
    content_json,
    created_at
)
VALUES
(
    1,
    1,
    NULL,
    1,
    1,
    'created',
    'Initial Chengdu itinerary',
    JSON_OBJECT(
        'days', 7,
        'hotel', '神秘小旅馆',
        'spots', JSON_ARRAY(
            '景点1',
            '景点2',
            '景点3'
        )
    ),
    NOW()
),
(
    2,
    1,
    1,
    1,
    2,
    'edited',
    'Updated hotel and attractions',
    JSON_OBJECT(
        'days', 7,
        'hotel', '神秘小旅馆二号',
        'spots', JSON_ARRAY(
            '景点4',
            '景点5'
        )
    ),
    NOW()
),
(
    3,
    2,
    NULL,
    2,
    1,
    'created',
    'Initial Xizang itinerary',
    JSON_OBJECT(
        'days', 5,
        'hotel', '神秘小旅馆三号',
        'spots', JSON_ARRAY(
            '景点6',
            '景点7'
        )
    ),
    NOW()
);

-- =========================
-- 更新 current_version_id
-- =========================

UPDATE trip_plans
SET current_version_id = 2
WHERE id = 1;

UPDATE trip_plans
SET current_version_id = 3
WHERE id = 2;

-- =========================
-- plan_tasks
-- =========================

INSERT INTO plan_tasks (
    id,
    user_id,
    plan_id,
    task_type,
    request_json,
    status,
    progress,
    result_version_id,
    error_message,
    created_at,
    updated_at
)
VALUES
(
    1,
    1,
    1,
    'generate_plan',
    JSON_OBJECT(
        'city', '成都',
        'days', 7
    ),
    'success',
    100,
    2,
    NULL,
    NOW(),
    NOW()
),
(
    2,
    2,
    2,
    'optimize_route',
    JSON_OBJECT(
        'optimize', true
    ),
    'running',
    60,
    NULL,
    NULL,
    NOW(),
    NOW()
),
(
    3,
    1,
    1,
    'regenerate_day',
    JSON_OBJECT(
        'day', 3
    ),
    'failed',
    30,
    NULL,
    'LLM timeout',
    NOW(),
    NOW()
);
