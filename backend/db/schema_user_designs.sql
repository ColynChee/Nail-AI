-- 我的设计（用户款式）表
-- 在 Supabase SQL Editor 执行一次即可。
CREATE TABLE IF NOT EXISTS user_designs (
  id                  BIGSERIAL PRIMARY KEY,
  client_id           TEXT NOT NULL,
  name                TEXT NOT NULL DEFAULT '我的设计',
  image_url           TEXT NOT NULL,                 -- 相对路径，如 /user_designs/<file>.jpg
  source              TEXT NOT NULL DEFAULT 'upload'
                        CHECK (source IN ('upload','ai','gallery')),
  style               TEXT,
  scenes              JSONB NOT NULL DEFAULT '[]'::jsonb,
  recommended_colors  JSONB NOT NULL DEFAULT '[]'::jsonb,
  description         TEXT,
  tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_designs_client
  ON user_designs (client_id, created_at DESC);
