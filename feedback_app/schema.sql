PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'faculty', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY,
    student_number TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INTEGER PRIMARY KEY,
    employee_number TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    FOREIGN KEY (faculty_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL UNIQUE,
    course_name TEXT NOT NULL,
    department TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS course_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    UNIQUE (faculty_id, course_id, semester),
    UNIQUE (assignment_id, course_id, semester)
);

CREATE TABLE IF NOT EXISTS student_courses (
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    PRIMARY KEY (student_id, course_id, semester),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    assignment_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    teaching_quality INTEGER NOT NULL CHECK (teaching_quality BETWEEN 1 AND 5),
    course_content INTEGER NOT NULL CHECK (course_content BETWEEN 1 AND 5),
    punctuality INTEGER NOT NULL CHECK (punctuality BETWEEN 1 AND 5),
    comments TEXT NOT NULL DEFAULT '' CHECK (length(comments) <= 1000),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id, course_id, semester)
        REFERENCES student_courses(student_id, course_id, semester) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id, course_id, semester)
        REFERENCES course_assignments(assignment_id, course_id, semester) ON DELETE CASCADE,
    UNIQUE (student_id, course_id, semester)
);

CREATE INDEX IF NOT EXISTS idx_feedback_assignment ON feedback(assignment_id, semester);

-- Demo password for each account: DemoPass123! (Werkzeug PBKDF2 hash).
INSERT OR IGNORE INTO users (user_id, email, password_hash, full_name, role) VALUES
    (1, 'admin@feedback.local', 'pbkdf2:sha256:600000$cH79JTkwVa1A8tpH$682a0588c3b27d644da37f5ef84da799db596e09bd678584742f5ab5d1594127', 'System Administrator', 'admin'),
    (2, 'faculty@feedback.local', 'pbkdf2:sha256:600000$cH79JTkwVa1A8tpH$682a0588c3b27d644da37f5ef84da799db596e09bd678584742f5ab5d1594127', 'Dr. Ada Faculty', 'faculty'),
    (3, 'student@feedback.local', 'pbkdf2:sha256:600000$cH79JTkwVa1A8tpH$682a0588c3b27d644da37f5ef84da799db596e09bd678584742f5ab5d1594127', 'Sam Student', 'student');

INSERT OR IGNORE INTO faculty (faculty_id, employee_number, department) VALUES (2, 'FAC-001', 'Computer Science');
INSERT OR IGNORE INTO students (student_id, student_number, department) VALUES (3, 'STU-001', 'Computer Science');
INSERT OR IGNORE INTO courses (course_id, course_code, course_name, department) VALUES
    (1, 'CS101', 'Introduction to Programming', 'Computer Science'),
    (2, 'CS205', 'Database Systems', 'Computer Science');
INSERT OR IGNORE INTO course_assignments (assignment_id, faculty_id, course_id, semester) VALUES
    (1, 2, 1, '2026-Fall'),
    (2, 2, 2, '2026-Fall');
INSERT OR IGNORE INTO student_courses (student_id, course_id, semester) VALUES
    (3, 1, '2026-Fall'),
    (3, 2, '2026-Fall');
