# Supabase Setup Operativo

Questa cartella contiene due livelli distinti:

- `schema.sql`: bootstrap riapplicabile. Serve per inizializzare o riallineare un progetto Supabase esistente senza dover ricordare a mano quali oggetti esistono gia.
- `migrations/001_user_profiles_bootstrap.sql`: migrazione iniziale immutabile. Serve se vuoi gestire il database con un flusso versionato.

## Scelta rapida

- Se stai configurando DietAPP manualmente dal dashboard Supabase, esegui `schema.sql` nell'SQL Editor.
- Se vuoi un flusso piu rigoroso con migrazioni versionate, applica la migrazione iniziale e poi aggiungi solo nuovi file numerati in `migrations/`.

## Setup iniziale di un nuovo progetto

1. Crea un progetto su Supabase.
2. Vai in `SQL Editor` ed esegui `supabase/schema.sql`.
3. Vai in `Authentication -> URL Configuration` e imposta:
   - `Site URL`: URL pubblico della tua app Streamlit.
   - `Additional Redirect URLs`: lo stesso URL pubblico, se usi recovery password.
4. Vai in `Authentication -> Users` e crea manualmente gli utenti autorizzati.
5. Copia nelle variabili ambiente dell'app:

```dotenv
SUPABASE_URL=https://tuo-progetto.supabase.co
SUPABASE_ANON_KEY=sb_publishable_o_anon_key
SUPABASE_PROFILE_TABLE=user_profiles
SUPABASE_AUTH_REDIRECT_URL=https://tuo-app.streamlit.app
```

6. Se usi recovery password, imposta il template email con un link di questo tipo:

```html
<h2>Reset Password</h2>
<p>Apri questo link per impostare una nuova password:</p>
<p>
  <a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery">
    Reimposta password
  </a>
</p>
```

## Riallineare un progetto esistente

Se il progetto Supabase esiste gia e vuoi solo verificare che tabella, colonne, policy, trigger e funzione siano allineati, riesegui `supabase/schema.sql`.

Lo script e stato reso riapplicabile per questi casi:

- colonne aggiunte in momenti diversi
- default o `not null` mancanti
- policy gia esistenti
- trigger gia presente

## Query utili di verifica

Verifica tabella e colonne:

```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public'
  and table_name = 'user_profiles'
order by ordinal_position;
```

Verifica policy RLS:

```sql
select policyname, cmd
from pg_policies
where schemaname = 'public'
  and tablename = 'user_profiles'
order by policyname;
```

Verifica trigger di aggiornamento:

```sql
select trigger_name
from information_schema.triggers
where event_object_schema = 'public'
  and event_object_table = 'user_profiles';
```

## Errori tipici in app e cosa controllare

- `Non riesco a leggere il profilo salvato su Supabase`: controlla tabella, colonne e policy `select`.
- `Il profilo non e stato salvato`: controlla policy `insert/update` e che l'app stia usando la `SUPABASE_ANON_KEY` corretta.
- `Non riesco a leggere strategia e piano salvati su Supabase`: controlla che le colonne JSON di strategia e piano siano presenti.
- `Strategia generata, ma non sono riuscito a salvarla su Supabase`: controlla policy `update` e i campi `request_payload`, `strategy_payload`, `strategy_source_label`, `strategy_warning`.
- `Dieta generata, ma non sono riuscito a salvarla su Supabase`: controlla anche `plan_payload`, `diet_source_label` e `diet_warning`.

## Strategia consigliata per le migrazioni

- `schema.sql` resta il bootstrap riapplicabile dell'ultimo stato desiderato.
- I file dentro `migrations/` non si modificano dopo essere stati applicati.
- Ogni cambiamento futuro di schema aggiunge un nuovo file numerato, per esempio `002_add_x.sql`.
- Quando aggiungi una nuova migrazione, aggiorna anche `schema.sql` per mantenere allineato il bootstrap completo.

## Checklist deploy privato

- `SUPABASE_URL` valorizzato
- `SUPABASE_ANON_KEY` valorizzato
- `SUPABASE_AUTH_REDIRECT_URL` uguale all'URL pubblico dell'app
- tabella `public.user_profiles` presente
- RLS attivo e policy create
- utenti autorizzati creati manualmente
- signup pubblico non esposto in app
