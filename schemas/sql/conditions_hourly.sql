-- conditions_hourly: one row per spot per hour, kept as history.
-- Written only by the publish step (service key). Read by the website and,
-- from M4, by the fishing-record snapshot.
--
-- What a row means: the LAST FORECAST made for that hour before the hour
-- began. These are forecast values, not measurements. The one exception is
-- river_flow_m3s, which is measured (see below).
--
-- Write rules for publish (upsert on spot_id + time_utc):
--   * hours that have not started yet: every column is overwritten each run;
--   * hours already in the past: only river_flow_m3s and updated_at change.
-- Running publish twice in the same hour therefore never adds rows.

create table if not exists public.conditions_hourly (
    spot_id          text             not null,
    time_utc         timestamptz      not null,   -- start of the hour

    -- same names and units as "hourly" in conditions/{spot_id}.json
    tide_height_m    double precision,
    tide_phase       text             check (tide_phase in ('rising', 'falling')),
    air_temp_c       double precision,
    precip_prob_pct  double precision check (precip_prob_pct between 0 and 100),
    weather_code     smallint,
    wind_speed_kmh   double precision check (wind_speed_kmh >= 0),
    wind_gust_kmh    double precision check (wind_gust_kmh >= 0),
    wind_dir_deg     double precision check (wind_dir_deg between 0 and 360),
    wind_relative    text             check (wind_relative in ('onshore', 'offshore', 'cross')),
    wave_height_m    double precision check (wave_height_m >= 0),
    swell_height_m   double precision check (swell_height_m >= 0),
    sea_temp_c       double precision,
    is_daylight      boolean          not null,

    -- measured: mean of the ECan readings inside this hour; null until the hour has data
    river_flow_m3s   double precision check (river_flow_m3s >= 0),

    -- filled in from M2 onwards
    score            double precision check (score between 0 and 100),
    ruleset_version  integer,

    updated_at       timestamptz      not null default now(),

    primary key (spot_id, time_utc)
);

-- Everyone may read; nobody may write through the public (anon) key.
-- The service key used by publish bypasses row level security.
alter table public.conditions_hourly enable row level security;

drop policy if exists "conditions_hourly is readable by everyone" on public.conditions_hourly;
create policy "conditions_hourly is readable by everyone"
    on public.conditions_hourly
    for select
    using (true);
