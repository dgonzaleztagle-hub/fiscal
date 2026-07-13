-- Estado efímero del sandbox público. No contiene secretos ni documentos tributarios reales.
CREATE TABLE IF NOT EXISTS public.fiscal_demo_sessions (
    session_id UUID PRIMARY KEY,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '14 days'),
    CONSTRAINT fiscal_demo_state_object CHECK (jsonb_typeof(state) = 'object')
);

ALTER TABLE public.fiscal_demo_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fiscal_demo_sessions FROM anon, authenticated;
CREATE INDEX IF NOT EXISTS fiscal_demo_sessions_expiry_idx
    ON public.fiscal_demo_sessions (expires_at);

COMMENT ON TABLE public.fiscal_demo_sessions IS
    'Sesiones sintéticas aisladas del sandbox Completo Fiscal; acceso exclusivo backend service_role.';
