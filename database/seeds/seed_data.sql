-- Default purposes
INSERT INTO purposes (name, slug, description, legal_basis_allowed, requires_explicit_consent) VALUES
('Marketing', 'marketing', 'Promotional campaigns and newsletters', ARRAY['consent','legitimate_interest'], true),
('Analytics', 'analytics', 'Website and app usage analytics', ARRAY['consent','legitimate_interest'], false),
('Personalization', 'personalization', 'Personalized content and recommendations', ARRAY['consent'], true),
('Support', 'support', 'Customer support and service', ARRAY['consent','contract'], false),
('Product Updates', 'product_updates', 'New features and announcements', ARRAY['consent','legitimate_interest'], false)
ON CONFLICT (slug) DO NOTHING;

-- Default channels
INSERT INTO channels (name, type, description, requires_opt_in) VALUES
('Email', 'email', 'Email communications', true),
('SMS', 'sms', 'Text messages', true),
('Push', 'push', 'Mobile push notifications', true),
('Web', 'web', 'Website banner', false),
('Voice', 'voice', 'Telephone calls', true)
ON CONFLICT (name) DO NOTHING;
