
CREATE SEQUENCE IF NOT EXISTS seq_role_id START 1;

CREATE TABLE IF NOT EXISTS Roles (
	role_id INTEGER PRIMARY KEY DEFAULT nextval('seq_role_id'),
	name VARCHAR(64) NOT NULL UNIQUE,
	description VARCHAR(255)
);


CREATE SEQUENCE IF NOT EXISTS seq_user_id START 1;

CREATE TABLE IF NOT EXISTS Users (
	user_id INTEGER PRIMARY KEY DEFAULT nextval('seq_user_id'),
	username VARCHAR(150) NOT NULL UNIQUE,
	email VARCHAR(254) UNIQUE,
	password_hash VARCHAR(255) NOT NULL,
	password_salt VARCHAR(128),
	is_active BOOLEAN DEFAULT TRUE,
	role_id INTEGER REFERENCES roles(role_id),
	created_at TIMESTAMP DEFAULT (now()),
	last_login TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS seq_session_id START 1;

CREATE TABLE IF NOT EXISTS Sessions (
	session_id INTEGER PRIMARY KEY DEFAULT nextval('seq_session_id'),
	user_id INTEGER NOT NULL REFERENCES users(user_id),
	session_token VARCHAR(512) NOT NULL UNIQUE,
	created_at TIMESTAMP DEFAULT (now()),
	expires_at TIMESTAMP,
	ip_address VARCHAR(45),
	user_agent VARCHAR(512)
);

CREATE SEQUENCE IF NOT EXISTS seq_project_id START 1;

CREATE TABLE IF NOT EXISTS Projects (
	project_id INTEGER PRIMARY KEY DEFAULT nextval('seq_project_id'),
	project_name VARCHAR(150) NOT NULL UNIQUE,
	created_at TIMESTAMP DEFAULT (now()),
);

CREATE SEQUENCE IF NOT EXISTS seq_project_role_id START 1;

CREATE TABLE IF NOT EXISTS ProjectRoles (
project_role_id INTEGER PRIMARY KEY DEFAULT nextval('seq_project_role_id'),
name VARCHAR(64) NOT NULL UNIQUE,
description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS ProjectUsers (
project_id INTEGER NOT NULL REFERENCES Projects(project_id),
user_id INTEGER NOT NULL REFERENCES Users(user_id),
project_role_id INTEGER REFERENCES ProjectRoles(project_role_id),
added_at TIMESTAMP DEFAULT (now()),
PRIMARY KEY (project_id, user_id)
);

CREATE SEQUENCE IF NOT EXISTS seq_infra_id START 1;

CREATE TABLE IF NOT EXISTS Infra (
	infra_id INTEGER PRIMARY KEY DEFAULT nextval('seq_infra_id'),
	project_id INTEGER NOT NULL REFERENCES Projects(project_id),
	infra_name VARCHAR(150) NOT NULL UNIQUE,
	infra_type VARCHAR(100) NOT NULL,
	infra_config TEXT NOT NULL,
	created_at TIMESTAMP DEFAULT (now()),
);

-- Populate

INSERT INTO Roles (name, description)
SELECT 
    'admin',
    'Administrator with full access'
WHERE NOT EXISTS (SELECT 1 FROM Roles WHERE name = 'admin');

INSERT INTO Roles (name, description)
SELECT 
    'user',
    'Regular authenticated user'
WHERE NOT EXISTS (SELECT 1 FROM Roles WHERE name = 'admin');

INSERT INTO ProjectRoles (name, description)
SELECT 
    'admin',
    'Administrator with full access'
WHERE NOT EXISTS (SELECT 1 FROM ProjectRoles WHERE name = 'admin');

INSERT INTO Users (username, email, password_hash, role_id, is_active)
SELECT
	'admin',
	'admin@example.com',
	'8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
	r.role_id,
	TRUE
FROM Roles r
WHERE r.name = 'admin'
AND NOT EXISTS (
	SELECT 1 FROM Users u WHERE u.username = 'admin'
);