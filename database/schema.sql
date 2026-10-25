-- SkillConnect database schema (MySQL 8, utf8mb4). REFERENCE COPY.
-- The app creates these tables itself with:  python create_tables.py
-- Use this file to read the design or to create the tables by hand.

CREATE TABLE locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  city VARCHAR(100) NOT NULL,
  area VARCHAR(100) NULL,
  pincode VARCHAR(10) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_location_city_area_pincode (city, area, pincode),
  KEY ix_locations_city (city)
);

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,          -- bcrypt hash, never the password
  role ENUM('CUSTOMER','PROVIDER','ADMIN') NOT NULL,
  phone VARCHAR(20) NULL,
  bio TEXT NULL,
  photo_url VARCHAR(500) NULL,
  location_id INT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
);

CREATE TABLE categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL UNIQUE,
  description VARCHAR(255) NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE skills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category_id INT NOT NULL,
  name VARCHAR(80) NOT NULL UNIQUE,
  description VARCHAR(255) NULL,
  created_by_id INT NULL,                       -- NULL = official skill, else the provider who added it
  created_at DATETIME NOT NULL,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
  FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE provider_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  description TEXT NULL,
  experience_years INT NULL,
  service_mode ENUM('REGULAR','NON_REGULAR','BOTH') NOT NULL,
  availability_notes VARCHAR(255) NULL,
  qualification VARCHAR(255) NULL,
  working_area VARCHAR(255) NULL,
  pricing_info VARCHAR(500) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT ck_provider_experience_years CHECK (experience_years IS NULL OR experience_years >= 0),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE provider_skills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  provider_profile_id INT NOT NULL,
  skill_id INT NOT NULL,
  UNIQUE KEY uq_provider_skill (provider_profile_id, skill_id),
  FOREIGN KEY (provider_profile_id) REFERENCES provider_profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE RESTRICT
);

CREATE TABLE availability (
  id INT AUTO_INCREMENT PRIMARY KEY,
  provider_profile_id INT NOT NULL,
  day_of_week ENUM('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY') NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  is_active INT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  KEY ix_availability_provider (provider_profile_id),
  FOREIGN KEY (provider_profile_id) REFERENCES provider_profiles(id) ON DELETE CASCADE
);

CREATE TABLE service_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  provider_id INT NOT NULL,
  skill_id INT NOT NULL,
  location_id INT NULL,
  service_mode ENUM('REGULAR','NON_REGULAR') NOT NULL,   -- REGULAR = long-term, NON_REGULAR = one-time
  scheduled_at DATETIME NULL,                            -- one-time requests
  duration_hours DECIMAL(5,2) NULL,
  message TEXT NULL,
  start_date DATE NULL,                                  -- regular requests
  end_date DATE NULL,
  working_days VARCHAR(80) NULL,                         -- e.g. MONDAY,WEDNESDAY
  start_time TIME NULL,
  end_time TIME NULL,
  address_details VARCHAR(255) NULL,
  status ENUM('PENDING','ACCEPTED','REJECTED','CANCELLED','COMPLETED') NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  KEY ix_requests_customer (customer_id),
  KEY ix_requests_provider (provider_id),
  KEY ix_requests_status (status),
  CONSTRAINT ck_request_not_self CHECK (customer_id <> provider_id),
  CONSTRAINT ck_request_duration_positive CHECK (duration_hours IS NULL OR duration_hours > 0),
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE RESTRICT,
  FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
);

CREATE TABLE messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  service_request_id INT NOT NULL,
  sender_id INT NOT NULL,
  body TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  KEY ix_messages_request (service_request_id),
  FOREIGN KEY (service_request_id) REFERENCES service_requests(id) ON DELETE CASCADE,
  FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  service_request_id INT NOT NULL UNIQUE,                -- one review per request
  reviewer_id INT NOT NULL,
  provider_id INT NOT NULL,
  rating INT NOT NULL,
  comment TEXT NULL,
  created_at DATETIME NOT NULL,
  KEY ix_reviews_provider (provider_id),
  CONSTRAINT ck_review_rating_range CHECK (rating >= 1 AND rating <= 5),
  FOREIGN KEY (service_request_id) REFERENCES service_requests(id) ON DELETE CASCADE,
  FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE CASCADE
);
