-- Supabase Storage policies for Borek Finance `invoices` bucket
-- Run in Supabase SQL editor after creating the bucket (Storage → New bucket → invoices, private).
--
-- Access model: the FastAPI backend uses the service role key for upload/download/delete.
-- End-user auth is app JWT (not Supabase Auth), so browser clients never talk to Storage directly.
-- Path convention: users/{user_id}/{uuid}_{filename}

-- Create bucket (private) if not exists
INSERT INTO storage.buckets (id, name, public)
VALUES ('invoices', 'invoices', false)
ON CONFLICT (id) DO UPDATE SET public = false;

-- Remove permissive defaults if present
DROP POLICY IF EXISTS "invoices_service_role_all" ON storage.objects;
DROP POLICY IF EXISTS "invoices_deny_anon" ON storage.objects;
DROP POLICY IF EXISTS "invoices_user_select_own" ON storage.objects;
DROP POLICY IF EXISTS "invoices_user_insert_own" ON storage.objects;
DROP POLICY IF EXISTS "invoices_user_delete_own" ON storage.objects;

-- Deny anonymous/public access
CREATE POLICY "invoices_deny_anon"
ON storage.objects FOR ALL
TO anon, public
USING (false)
WITH CHECK (false);

-- Service role (backend) full access to invoices bucket
CREATE POLICY "invoices_service_role_all"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'invoices')
WITH CHECK (bucket_id = 'invoices');

-- Optional: future Supabase Auth direct uploads — user may only access own folder
-- Uncomment when migrating to Supabase Auth JWT in Storage requests.
--
-- CREATE POLICY "invoices_user_select_own"
-- ON storage.objects FOR SELECT
-- TO authenticated
-- USING (
--   bucket_id = 'invoices'
--   AND (storage.foldername(name))[1] = 'users'
--   AND (storage.foldername(name))[2] = auth.uid()::text
-- );
--
-- CREATE POLICY "invoices_user_insert_own"
-- ON storage.objects FOR INSERT
-- TO authenticated
-- WITH CHECK (
--   bucket_id = 'invoices'
--   AND (storage.foldername(name))[1] = 'users'
--   AND (storage.foldername(name))[2] = auth.uid()::text
-- );
--
-- CREATE POLICY "invoices_user_delete_own"
-- ON storage.objects FOR DELETE
-- TO authenticated
-- USING (
--   bucket_id = 'invoices'
--   AND (storage.foldername(name))[1] = 'users'
--   AND (storage.foldername(name))[2] = auth.uid()::text
-- );
