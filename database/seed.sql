-- ============================================================
-- GNANI AI — Demo Seed Data
-- Acme AI Demo Organization with fake business data
-- ============================================================

-- Demo Organization
INSERT INTO organizations (id, name, slug, is_demo) VALUES
  ('00000000-0000-0000-0000-000000000001', 'Acme AI Demo', 'acme-demo', TRUE);

-- Demo Users
INSERT INTO users (id, organization_id, email, full_name, role) VALUES
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'admin@acme-demo.com', 'Demo Admin', 'admin'),
  ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'agent@acme-demo.com', 'Agent User', 'member');

-- Permissions for admin user (full access)
INSERT INTO permissions (user_id, organization_id, scope) VALUES
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'crm.read'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'crm.write'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'gmail.read'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'gmail.send'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'slack.read'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'slack.send'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'whatsapp.send'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'calendar.read'),
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'calendar.write');

-- Registered Tools (Tool Registry seeded into DB)
INSERT INTO tools (name, description, integration, risk_level, required_permission, input_schema, output_schema) VALUES
  ('gmail.search', 'Search and read Gmail messages', 'gmail', 'low', 'gmail.read',
    '{"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":10}},"required":["query"]}',
    '{"type":"object","properties":{"emails":{"type":"array"},"count":{"type":"integer"}}}'),

  ('gmail.send', 'Send an email via Gmail', 'gmail', 'medium', 'gmail.send',
    '{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"},"cc":{"type":"string"}},"required":["to","subject","body"]}',
    '{"type":"object","properties":{"message_id":{"type":"string"},"status":{"type":"string"}}}'),

  ('crm.find_customer', 'Find customer records by name, email, or ID', 'crm', 'low', 'crm.read',
    '{"type":"object","properties":{"query":{"type":"string"},"customer_id":{"type":"string"},"email":{"type":"string"}}}',
    '{"type":"object","properties":{"customers":{"type":"array"},"count":{"type":"integer"}}}'),

  ('crm.find_order', 'Find order records by customer or status', 'crm', 'low', 'crm.read',
    '{"type":"object","properties":{"customer_id":{"type":"string"},"status":{"type":"string"},"delayed_more_than_days":{"type":"integer"}}}',
    '{"type":"object","properties":{"orders":{"type":"array"},"count":{"type":"integer"}}}'),

  ('crm.create_ticket', 'Create a support ticket for a customer/order issue', 'crm', 'medium', 'crm.write',
    '{"type":"object","properties":{"customer_id":{"type":"string"},"order_id":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high","critical"]},"title":{"type":"string"},"description":{"type":"string"}},"required":["customer_id","priority","title","description"]}',
    '{"type":"object","properties":{"ticket_id":{"type":"string"},"status":{"type":"string"}}}'),

  ('crm.update_customer', 'Update customer data in CRM', 'crm', 'medium', 'crm.write',
    '{"type":"object","properties":{"customer_id":{"type":"string"},"updates":{"type":"object"}},"required":["customer_id","updates"]}',
    '{"type":"object","properties":{"customer_id":{"type":"string"},"updated":{"type":"boolean"}}}'),

  ('slack.send_message', 'Send a message to a Slack channel or user', 'slack', 'medium', 'slack.send',
    '{"type":"object","properties":{"channel":{"type":"string"},"message":{"type":"string"},"thread_ts":{"type":"string"}},"required":["channel","message"]}',
    '{"type":"object","properties":{"ts":{"type":"string"},"channel":{"type":"string"},"ok":{"type":"boolean"}}}'),

  ('whatsapp.send_message', 'Send a WhatsApp message to a phone number', 'whatsapp', 'medium', 'whatsapp.send',
    '{"type":"object","properties":{"to":{"type":"string"},"message":{"type":"string"}},"required":["to","message"]}',
    '{"type":"object","properties":{"message_id":{"type":"string"},"status":{"type":"string"}}}'),

  ('calendar.find_slot', 'Find available calendar slots', 'calendar', 'low', 'calendar.read',
    '{"type":"object","properties":{"attendees":{"type":"array"},"duration_minutes":{"type":"integer"},"within_days":{"type":"integer","default":7}},"required":["attendees","duration_minutes"]}',
    '{"type":"object","properties":{"slots":{"type":"array"}}}'),

  ('calendar.create_event', 'Create a calendar event', 'calendar', 'medium', 'calendar.write',
    '{"type":"object","properties":{"title":{"type":"string"},"start_time":{"type":"string"},"end_time":{"type":"string"},"attendees":{"type":"array"},"description":{"type":"string"}},"required":["title","start_time","end_time"]}',
    '{"type":"object","properties":{"event_id":{"type":"string"},"status":{"type":"string"}}}');

-- Demo Integrations (connected services for Acme Demo)
INSERT INTO integrations (organization_id, service, display_name, is_active, config_json) VALUES
  ('00000000-0000-0000-0000-000000000001', 'gmail',    'Acme Demo Gmail',    TRUE, '{"email":"demo@acme-demo.com"}'),
  ('00000000-0000-0000-0000-000000000001', 'slack',    'Acme Demo Slack',    TRUE, '{"workspace":"acme-demo"}'),
  ('00000000-0000-0000-0000-000000000001', 'crm',      'Acme Demo CRM',      TRUE, '{"provider":"mock","base_url":"http://localhost:8001"}'),
  ('00000000-0000-0000-0000-000000000001', 'whatsapp', 'Acme Demo WhatsApp', TRUE, '{"phone_number_id":"DEMO_PHONE_ID"}'),
  ('00000000-0000-0000-0000-000000000001', 'calendar', 'Acme Demo Calendar', TRUE, '{"calendar_id":"demo@acme-demo.com"}');

