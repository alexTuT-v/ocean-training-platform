CREATE TABLE IF NOT EXISTS tenants (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  email TEXT NOT NULL UNIQUE,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  UNIQUE (id, tenant_id)
);

CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  UNIQUE (id, tenant_id)
);

CREATE TABLE IF NOT EXISTS learners (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  UNIQUE (id, tenant_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  course_id INTEGER NOT NULL,
  learner_id INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'INCOMPLETE')),
  completed_at_utc TEXT,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  FOREIGN KEY (course_id, tenant_id) REFERENCES courses(id, tenant_id),
  FOREIGN KEY (learner_id, tenant_id) REFERENCES learners(id, tenant_id),
  UNIQUE (tenant_id, course_id, learner_id)
);

CREATE TABLE IF NOT EXISTS certificates (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  course_id INTEGER NOT NULL,
  learner_id INTEGER NOT NULL,
  serial_number TEXT NOT NULL UNIQUE,
  issued_at_utc TEXT NOT NULL,
  issued_local_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'REVOKED')),
  revoked_at_utc TEXT,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  FOREIGN KEY (course_id, tenant_id) REFERENCES courses(id, tenant_id),
  FOREIGN KEY (learner_id, tenant_id) REFERENCES learners(id, tenant_id),
  FOREIGN KEY (tenant_id, course_id, learner_id) REFERENCES enrollments(tenant_id, course_id, learner_id),
  UNIQUE (id, tenant_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_certificate
  ON certificates(tenant_id, course_id, learner_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS certificates_tenant_date ON certificates(tenant_id, issued_local_date DESC, id);
CREATE INDEX IF NOT EXISTS certificates_tenant_serial ON certificates(tenant_id, serial_number);

CREATE TABLE IF NOT EXISTS idempotency_records (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  actor_id INTEGER NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL,
  operation_type TEXT NOT NULL,
  response_status INTEGER,
  response_body_json TEXT,
  created_at_utc TEXT NOT NULL,
  completed_at_utc TEXT,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  FOREIGN KEY (actor_id, tenant_id) REFERENCES admins(id, tenant_id),
  UNIQUE (tenant_id, actor_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  certificate_id INTEGER NOT NULL,
  actor_id INTEGER NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('ISSUED', 'REVOKED')),
  occurred_at_utc TEXT NOT NULL,
  idempotency_record_id INTEGER,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  FOREIGN KEY (certificate_id, tenant_id) REFERENCES certificates(id, tenant_id),
  FOREIGN KEY (actor_id, tenant_id) REFERENCES admins(id, tenant_id),
  FOREIGN KEY (idempotency_record_id) REFERENCES idempotency_records(id),
  UNIQUE (certificate_id, event_type)
);
