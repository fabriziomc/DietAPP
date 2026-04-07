create table if not exists public.user_profiles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    form_values jsonb not null default '{}'::jsonb,
    request_payload jsonb,
    strategy_payload jsonb,
    strategy_source_label text,
    strategy_warning text,
    plan_payload jsonb,
    diet_source_label text,
    diet_warning text,
    updated_at timestamptz not null default timezone('utc', now())
);

alter table public.user_profiles add column if not exists request_payload jsonb;
alter table public.user_profiles add column if not exists strategy_payload jsonb;
alter table public.user_profiles add column if not exists strategy_source_label text;
alter table public.user_profiles add column if not exists strategy_warning text;
alter table public.user_profiles add column if not exists plan_payload jsonb;
alter table public.user_profiles add column if not exists diet_source_label text;
alter table public.user_profiles add column if not exists diet_warning text;

alter table public.user_profiles enable row level security;

create policy "Users can read their own profile"
on public.user_profiles
for select
using (auth.uid() = user_id);

create policy "Users can insert their own profile"
on public.user_profiles
for insert
with check (auth.uid() = user_id);

create policy "Users can update their own profile"
on public.user_profiles
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create or replace function public.set_user_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists user_profiles_set_updated_at on public.user_profiles;

create trigger user_profiles_set_updated_at
before update on public.user_profiles
for each row
execute function public.set_user_profiles_updated_at();