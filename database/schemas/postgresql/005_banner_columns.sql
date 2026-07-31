-- banner_service.create/update/publish reference these but the initial schema
-- never added them: purposes/channels drive banner targeting, archived_at is
-- set when publish() retires the previously-live banner of the same type.
ALTER TABLE banners ADD COLUMN IF NOT EXISTS purposes UUID[] DEFAULT '{}';
ALTER TABLE banners ADD COLUMN IF NOT EXISTS channels UUID[] DEFAULT '{}';
ALTER TABLE banners ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
