-- =====================================================================
-- Portal de Ocorrências (Django): preparação do Supabase (spec 015)
--
-- Rode UMA vez no SQL Editor do Supabase. Antes, troque a senha abaixo por
-- uma senha forte e guarde-a: ela vai na DATABASE_URL (Vercel e .env local).
--
-- Por que um usuário e um schema próprios: o schema `public` é exposto pela
-- API do Supabase (chave anônima). As tabelas do Django ficam no schema
-- `django`, que a API não expõe, acessadas só pelo usuário `django_app`.
-- O check ocorrencias.E001 impede o migrate de rodar em outro schema.
-- =====================================================================

-- 1. Usuário do Django (troque a senha).
create role django_app with login password 'TROQUE-POR-UMA-SENHA-FORTE';

-- 2. Schema próprio, do qual o django_app é dono.
create schema if not exists django authorization django_app;

-- 3. Toda conexão do django_app cai no schema django.
alter role django_app set search_path = django;

-- 4. Nenhum acesso pela API do Supabase (anon/authenticated) nem por outros usuários.
revoke all on schema django from public, anon, authenticated;

-- 5. Bucket PRIVADO para os anexos (o Django gera URLs assinadas de 60 s).
insert into storage.buckets (id, name, public)
values ('anexos-django', 'anexos-django', false)
on conflict (id) do nothing;

-- Conferência: deve listar o schema django com dono django_app e o bucket privado.
select nspname as schema, pg_get_userbyid(nspowner) as dono from pg_namespace where nspname = 'django';
select id, public from storage.buckets where id = 'anexos-django';
