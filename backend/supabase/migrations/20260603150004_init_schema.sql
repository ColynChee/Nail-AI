-- Core schema for Nail-AI on Supabase/Postgres.
-- This migration is intentionally permissive so the app can write logs
-- before a full design seed exists in the database.

create extension if not exists vector;

create table if not exists designs (
  id text primary key,
  name text not null,
  image text,
  emoji text,
  bg text,
  price text,
  enhanced_hash text,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists designs_created_at_idx on designs (created_at desc);
create index if not exists designs_enhanced_hash_idx on designs (enhanced_hash);

create table if not exists molds (
  id bigserial primary key,
  design_id text not null,
  finger_idx smallint not null check (finger_idx between 0 and 4),
  path text not null,
  mime_type text not null default 'image/png',
  created_at timestamptz not null default now(),
  unique (design_id, finger_idx)
);

create index if not exists molds_design_id_idx on molds (design_id);

create table if not exists try_on_logs (
  id bigserial primary key,
  design_id text,
  success boolean not null default false,
  message text,
  mode text,
  n_applied integer,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists try_on_logs_created_at_idx on try_on_logs (created_at desc);
create index if not exists try_on_logs_design_id_idx on try_on_logs (design_id);
create index if not exists try_on_logs_success_idx on try_on_logs (success);

create table if not exists user_profiles (
  client_id text primary key,
  name text,
  avatar text,
  age integer,
  bio text,
  skin_color_code text,
  skin_tone_label text,
  skin_tone_source text,
  recommended_style_ids jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists user_profiles_updated_at_idx on user_profiles (updated_at desc);
create index if not exists user_profiles_skin_color_code_idx on user_profiles (skin_color_code);
