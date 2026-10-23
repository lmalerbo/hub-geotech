-- Stub local do PostGIS (só para a cadeia de migrações rodar; geometria vira texto).
create schema if not exists extensions;
create domain extensions.geometry as text;
do $$ declare s text; begin
  foreach s in array array['extensions','public','hub'] loop
    execute format('create schema if not exists %I', s);
    execute format('create function %I.st_astext(text) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_asgeojson(text, int default 9) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_buffer(text, float8) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_force2d(text) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_geomfromtext(text, int default 0) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_multi(text) returns text language sql immutable as ''select $1''', s);
    execute format('create function %I.st_transform(text, int) returns text language sql immutable as ''select $1''', s);
    execute format('create aggregate %I.st_union(text) (sfunc = textcat, stype = text, initcond = '''')', s);
  end loop; end $$;
create schema if not exists storage;
create table storage.buckets (id text primary key, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
create table storage.objects (id uuid primary key default gen_random_uuid(), bucket_id text, name text, owner uuid, metadata jsonb);
alter table storage.objects enable row level security;
create function storage.foldername(text) returns text[] language sql immutable as 'select string_to_array($1, ''/'')';
grant usage on schema storage, extensions to anon, authenticated, service_role;
