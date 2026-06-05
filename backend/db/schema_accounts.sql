-- 账号系统 + 收藏上云
-- 在 Supabase SQL Editor 执行一次即可。

CREATE TABLE IF NOT EXISTS accounts (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  client_key    TEXT NOT NULL UNIQUE,   -- 登录后作为 client_id 使用
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_wishlist (
  id         BIGSERIAL PRIMARY KEY,
  client_id  TEXT NOT NULL,
  name       TEXT NOT NULL,
  emoji      TEXT,
  price      TEXT,
  bg         TEXT,
  image      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (client_id, name)
);

CREATE INDEX IF NOT EXISTS idx_user_wishlist_client ON user_wishlist (client_id);
