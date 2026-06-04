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
