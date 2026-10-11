-- DRAFT for M4 - not yet confirmed by Liang, not yet run anywhere.
--
-- records: one row per fishing trip, including the trips with no fish.
-- Everyone may read. Only a signed-in user may write, and public sign-up is
-- switched off in Supabase, so in practice only Liang can.

create table if not exists public.records (
    id                  uuid         primary key default gen_random_uuid(),

    -- filled in by hand
    spot_id             text         not null,                 -- an id from config/spots.yaml
    started_at          timestamptz  not null,                 -- may be in the past: trips can be logged later
    ended_at            timestamptz  not null,
    outcome             text         not null check (outcome in ('catch', 'blank')),
    catches             jsonb        not null default '[]',    -- [{"species": "kahawai", "count": 2, "size_cm": 45}], empty for a blank trip
    bait_and_rig        text,
    notes               text,
    photos              text[]       not null default '{}',    -- paths inside the record-photos bucket
    video_url           text         check (video_url is null or video_url ~ '^https://(www\.)?(youtube\.com|youtu\.be)/'),

    -- filled in automatically when the record is saved, from conditions_hourly;
    -- stored here so the record keeps them even if the history table changes later
    conditions_snapshot jsonb,                                  -- one entry per hour of the trip; null when there is no history for that time
    score_snapshot      jsonb,                                  -- {"hours": [{"time_utc", "score"}], "mean_score", "ruleset_version"}; null likewise

    created_at          timestamptz  not null default now(),
    updated_at          timestamptz  not null default now(),

    check (ended_at > started_at),
    check (outcome = 'catch' or catches = '[]'::jsonb)
);

create index if not exists records_started_at_idx on public.records (started_at desc);

alter table public.records enable row level security;

drop policy if exists "records are readable by everyone" on public.records;
create policy "records are readable by everyone" on public.records
    for select using (true);

drop policy if exists "signed-in users can add records" on public.records;
create policy "signed-in users can add records" on public.records
    for insert to authenticated with check (true);

drop policy if exists "signed-in users can change records" on public.records;
create policy "signed-in users can change records" on public.records
    for update to authenticated using (true) with check (true);

drop policy if exists "signed-in users can delete records" on public.records;
create policy "signed-in users can delete records" on public.records
    for delete to authenticated using (true);

-- Photos: a public bucket anyone can view; only a signed-in user may add, replace or remove files.
insert into storage.buckets (id, name, public)
values ('record-photos', 'record-photos', true)
on conflict (id) do nothing;

drop policy if exists "record photos are viewable by everyone" on storage.objects;
create policy "record photos are viewable by everyone" on storage.objects
    for select using (bucket_id = 'record-photos');

drop policy if exists "signed-in users can add record photos" on storage.objects;
create policy "signed-in users can add record photos" on storage.objects
    for insert to authenticated with check (bucket_id = 'record-photos');

drop policy if exists "signed-in users can change record photos" on storage.objects;
create policy "signed-in users can change record photos" on storage.objects
    for update to authenticated using (bucket_id = 'record-photos');

drop policy if exists "signed-in users can delete record photos" on storage.objects;
create policy "signed-in users can delete record photos" on storage.objects
    for delete to authenticated using (bucket_id = 'record-photos');
