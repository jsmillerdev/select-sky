-- A phone's position, parked for a few minutes until the badge that showed the QR code collects it.
-- The sky Edge Function is the only caller: it writes the row and deletes it as it hands it out.

create table if not exists public.sky_handoff (
  code       text primary key check (code ~ '^[A-HJ-KM-NP-Z2-9]{6}$'),
  lat        double precision not null check (lat between -90 and 90),
  lon        double precision not null check (lon between -180 and 180),
  acc        real,
  created_at timestamptz not null default now()
);

comment on table public.sky_handoff is
  'One-time hand-off of a phone position to a Select Sky badge. The phone page stores it under the '
  'badge''s random code and the badge''s next request claims and deletes it. Rows older than 10 minutes '
  'are ignored and purged by the sky Edge Function, the only code that touches this table.';

-- The expiry purge filters on created_at.
create index if not exists sky_handoff_created_at_idx on public.sky_handoff (created_at);

-- Not part of the Data API: the API roles have no table privileges, and RLS is on with a rule that
-- denies them every row, which also keeps the advisor from reading the missing policy as a mistake.
-- service_role (the Edge Function's secret key) bypasses RLS but still needs its grant.
alter table public.sky_handoff enable row level security;
revoke all on table public.sky_handoff from anon, authenticated;
grant select, insert, update, delete on table public.sky_handoff to service_role;

drop policy if exists sky_handoff_deny_api on public.sky_handoff;
create policy sky_handoff_deny_api on public.sky_handoff
  for all to anon, authenticated using (false) with check (false);
