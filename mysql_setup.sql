CREATE DATABASE IF NOT EXISTS ev_fire_guard
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'evguard'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON ev_fire_guard.* TO 'evguard'@'localhost';
FLUSH PRIVILEGES;

