CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(100) PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    language VARCHAR(100) DEFAULT 'en',
    country VARCHAR(100) DEFAULT 'US',
    created_by VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS event_courses (
    event_id VARCHAR(100) REFERENCES events(id) ON DELETE CASCADE,
    course_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (event_id, course_id)
);

CREATE TABLE IF NOT EXISTS running_logs (
    event_id VARCHAR(100) PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    event_name VARCHAR(255) NOT NULL,
    cloud_run_service_name VARCHAR(255) NOT NULL,
    cloud_run_url VARCHAR(255),
    scheduled_start_date DATE NOT NULL,
    scheduled_end_date DATE NOT NULL,
    actual_datetime_started TIMESTAMP,
    actual_datetime_ended TIMESTAMP,
    repos_to_read JSONB,
    folders_to_load JSONB,
    status VARCHAR(50) DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS courses (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    repo_url TEXT NOT NULL,
    directory_root VARCHAR(255) DEFAULT '/',
    is_published BOOLEAN DEFAULT TRUE,
    last_eval_date TIMESTAMP DEFAULT NULL,
    eval_score VARCHAR(50) DEFAULT '0%',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS eval_log (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) REFERENCES events(id) ON DELETE CASCADE,
    course_id VARCHAR(255) REFERENCES courses(id) ON DELETE CASCADE,
    eval_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(50),
    question_number INT,
    question TEXT,
    prefer_answer TEXT,
    ta_answer TEXT
);

CREATE TABLE IF NOT EXISTS eval_suggestion (
    id SERIAL PRIMARY KEY,
    course_id VARCHAR(255) REFERENCES courses(id) ON DELETE CASCADE,
    eval_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    score VARCHAR(50),
    suggest_update TEXT
);

INSERT INTO courses (id, name, repo_url, directory_root, is_published, last_eval_date, eval_score, last_update_date)
VALUES 
    ('level-0', 'Way Back Home level 0', 'https://github.com/gca-americas/virtual-ta-skills.git', '/', TRUE, '2026-03-26T13:57:19.743785Z', '0%', '2026-03-29T18:59:12.033783Z'),
    ('level-1', 'Way Back Home level 1', 'https://github.com/gca-americas/virtual-ta-skills.git', '/', TRUE, '2026-03-26T13:57:19.743785Z', '0%', '2026-03-29T18:59:12.033783Z'),
    ('level-2', 'Way Back Home level 2', 'https://github.com/gca-americas/virtual-ta-skills.git', '/', TRUE, '2026-03-26T13:57:19.743785Z', '0%', '2026-03-29T18:59:12.033783Z'),
    ('level-3', 'Way Back Home level 3', 'https://github.com/gca-americas/virtual-ta-skills.git', '/', TRUE, '2026-03-26T13:57:19.743785Z', '0%', '2026-03-29T18:59:12.033783Z'),
    ('adk-crash-course-b-to-e', 'ADK Crash Course - From Beginner To Expert', 'https://github.com/gca-americas/virtual-ta-skills.git', '/', TRUE, '2026-03-27T15:14:26.254317Z', '0%', '2026-03-29T18:59:12.033783Z')
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    repo_url = EXCLUDED.repo_url,
    directory_root = EXCLUDED.directory_root,
    is_published = EXCLUDED.is_published,
    last_eval_date = EXCLUDED.last_eval_date,
    eval_score = EXCLUDED.eval_score,
    last_update_date = EXCLUDED.last_update_date;

CREATE TABLE IF NOT EXISTS admins (
    email VARCHAR(255) PRIMARY KEY,
    role VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
