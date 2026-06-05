# DietAPP

Applicazione web in Python + Streamlit per pianificare la dieta settimanale di una coppia con regimi alimentari diversi, riducendo al minimo il lavoro in cucina.

## Documentazione

- guida utente: [GUIDA_UTENTE.md](GUIDA_UTENTE.md)
- setup e operativita Supabase: [supabase/README.md](supabase/README.md)

## Cosa fa

- raccoglie i profili alimentari di due persone
- raccoglie anche eta, sesso, altezza, peso, obiettivo peso, attivita motoria descrittiva e l'eventuale uso per-persona di proteine in polvere
- genera prima una strategia benessere personalizzata e poi il piano settimanale con colazione, pranzo e cena
- cerca di riusare basi comuni tra versione onnivora e vegetariana
- privilegia batch cooking, avanzi intelligenti e ingredienti ricorrenti
- produce una lista della spesa aggregata con quantita quando disponibili
- usa i valori del file `.env` per OpenAI, Groq o OpenRouter, altrimenti passa a un planner locale deterministico con ricette italiane
- puo salvare localmente il profilo della coppia e ricaricarlo ai successivi avvii

## Avvio rapido

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
copy .env.example .env
streamlit run app.py
```

Se ti serve solo l'ambiente runtime, per esempio su Streamlit Cloud o per un avvio locale minimale, puoi usare anche:

```bash
pip install -r requirements.txt
```

## Comandi di sviluppo

```bash
python -m pytest
python -m ruff check .
python -m mypy
streamlit run app.py
```

## Configurazione AI

Se vuoi usare il generatore AI:

1. imposta `AI_PROVIDER=openai` oppure `AI_PROVIDER=groq` nel file `.env`
2. se usi OpenAI compila `OPENAI_API_KEY` e opzionalmente `OPENAI_MODEL`
3. se usi Groq compila `GROQ_API_KEY` e opzionalmente `GROQ_MODEL`
4. se usi OpenRouter compila `OPENROUTER_API_KEY` e opzionalmente `OPENROUTER_MODEL`

Esempio OpenRouter con modello gratuito:

```dotenv
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=google/gemma-4-31b-it:free
OPENROUTER_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,qwen/qwen3-next-80b-a3b-instruct:free,openai/gpt-oss-120b:free
OPENROUTER_SITE_URL=https://tuo-app.streamlit.app
OPENROUTER_APP_NAME=DietAPP
```

`OPENROUTER_SITE_URL` e `OPENROUTER_APP_NAME` sono opzionali ma consigliati: vengono inviati come header `HTTP-Referer` e `X-OpenRouter-Title` nelle richieste API.
`OPENROUTER_FALLBACK_MODELS` e opzionale: se il modello principale e rate-limited, OpenRouter provera automaticamente questi modelli in ordine usando il routing `fallback`.
Se `AI_PROVIDER=openrouter` e hai anche `GROQ_API_KEY`, l'app prova prima OpenRouter, poi Groq, e solo dopo passa al planner locale.

Modelli consigliati su Groq per questa app:

- `llama-3.3-70b-versatile`: scelta migliore per qualita e aderenza al JSON
- `llama-3.1-8b-instant`: scelta migliore per velocita e costo ridotto

Modelli OpenRouter sensati per iniziare:

- `google/gemma-4-31b-it:free`: buon punto di partenza per test e fallback a costo zero
- `google/gemma-4-26b-a4b-it:free`: alternativa gratuita spesso piu leggera
- `meta-llama/llama-3.3-70b-instruct:free`: buon fallback gratuito orientato a JSON e istruzioni
- `qwen/qwen3-next-80b-a3b-instruct:free`: altro fallback gratuito valido quando il ramo Google e saturo
- `openai/gpt-oss-120b:free`: fallback aggiuntivo se vuoi distribuire il carico su famiglie diverse

Se la chiave non e presente, l'app resta comunque utilizzabile tramite il planner locale.
Il planner locale ora filtra gli ingredienti esclusi, usa davvero budget e cucine preferite per ordinare i template, mantiene le proposte in un perimetro di ricette italiane domestiche e, nei casi piu stretti, prova a sostituire automaticamente gli ingredienti vietati con equivalenti compatibili.

## Come registrarsi a OpenRouter

1. vai su `https://openrouter.ai/` e crea un account
2. entra nella dashboard e genera una API key personale
3. scegli un modello, per esempio `google/gemma-4-31b-it:free` se vuoi partire dal tier gratuito
4. copia la chiave nel file `.env` come `OPENROUTER_API_KEY`
5. imposta `AI_PROVIDER=openrouter`
6. se l'app e pubblicata, aggiungi anche `OPENROUTER_SITE_URL` con l'URL pubblico della tua app e lascia `OPENROUTER_APP_NAME=DietAPP`
7. opzionalmente imposta `OPENROUTER_FALLBACK_MODELS` con una lista separata da virgole di modelli alternativi, per esempio `meta-llama/llama-3.3-70b-instruct:free,qwen/qwen3-next-80b-a3b-instruct:free,openai/gpt-oss-120b:free`

Nota pratica: i modelli gratuiti su OpenRouter possono avere disponibilita e rate limit variabili nel tempo, quindi conviene tenerlo come provider alternativo accanto a Groq e configurare uno o piu fallback automatici.

## Accesso riservato e profili cloud

Se vuoi che la app pubblicata non sia liberamente utilizzabile e che ogni utente ritrovi il proprio profilo anche dopo un deploy, puoi usare Supabase.

- il piano Free e sufficiente per questa app: include autenticazione, database Postgres e 500 MB di spazio
- attenzione solo a un limite pratico del piano Free: il progetto viene messo in pausa dopo 1 settimana di inattivita
- nell'app va usata la `SUPABASE_ANON_KEY`, non la service role key

Variabili da impostare in `.env` o nei secrets di Streamlit:

```dotenv
SUPABASE_URL=https://tuo-progetto.supabase.co
SUPABASE_ANON_KEY=sb_publishable_o_anon_key
SUPABASE_PROFILE_TABLE=user_profiles
SUPABASE_AUTH_REDIRECT_URL=https://tuo-app.streamlit.app
```

La UI non espone signup pubblico. Per mantenere l'app privata:

1. crea la tabella e le policy usando [supabase/schema.sql](supabase/schema.sql)
2. in Supabase vai in `Authentication -> Users`
3. crea manualmente gli utenti autorizzati
4. usa nell'app solo il login email/password

`supabase/schema.sql` e ora un bootstrap riapplicabile.
Se vuoi invece una base piu rigorosa e versionata, usa la migrazione iniziale in [supabase/migrations/001_user_profiles_bootstrap.sql](supabase/migrations/001_user_profiles_bootstrap.sql) e poi aggiungi solo nuove migrazioni numerate.
Dettagli operativi in [supabase/README.md](supabase/README.md).

Quando Supabase e configurato:

- l'app chiede login prima di mostrare il planner
- il profilo coppia viene salvato per `user_id` nel database
- l'ultima strategia benessere e l'ultimo piano settimanale vengono salvati e ricaricati automaticamente se il profilo non e cambiato
- i dati non dipendono piu dal filesystem locale di Streamlit Cloud
- il piano mostra porzioni, quantita ingredienti, spesa aggregata e controlli automatici di coerenza

Per il reset password via email:

1. aggiungi l'URL pubblico della tua app sia in `Authentication -> URL Configuration -> Site URL` sia tra gli `Additional Redirect URLs`
2. imposta `SUPABASE_AUTH_REDIRECT_URL` con lo stesso URL pubblico dell'app
3. in `Authentication -> Email Templates -> Reset Password` usa un link costruito con `TokenHash`, ad esempio:

```html
<h2>Reset Password</h2>
<p>Apri questo link per impostare una nuova password:</p>
<p>
	<a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery">
		Reimposta password
	</a>
</p>
```

Questo evita il fragment dell'implicit flow e permette all'app Streamlit di verificare il recovery link lato server con `verify_otp(...)`.

## Profilo salvato

Dentro l'app puoi usare il pulsante `Salva profilo coppia`.
I valori dei due profili e delle preferenze di cucina vengono salvati localmente in `data/household_profile.json` e ricaricati automaticamente dopo refresh o riavvio.

Se Supabase e configurato, il salvataggio locale viene sostituito da un salvataggio cloud per-account.
Quando il profilo cambia, l'app invalida la strategia e il piano precedenti per evitare che vengano mostrati risultati non piu coerenti.

## Nuovo flusso

1. inserisci per ciascuna persona dati fisici, obiettivo peso, regime alimentare, attivita motoria e vincoli alimentari
2. l'app genera una strategia benessere con focus e target derivati
3. da quella strategia costruisce il piano settimanale condiviso per la coppia

## Struttura

- `app.py`: interfaccia Streamlit
- `src/dietapp/models.py`: modelli dati
- `src/dietapp/planner.py`: generazione piano AI + fallback locale
- `src/dietapp/auth.py`: login Supabase e gestione sessione
- `src/dietapp/persistence.py`: persistenza locale o su Supabase di profilo, strategia e piano
- `src/dietapp/formatters.py`: export markdown e metriche
- `GUIDA_UTENTE.md`: guida pratica per chi usa l'app
- `supabase/README.md`: setup, verifica e deploy privato con Supabase
- `supabase/schema.sql`: tabella e policy RLS per profilo, strategia e piano utente
- `tests/test_planner.py`: test base del planner locale

## Tooling progetto

- packaging e configurazione centralizzati in `pyproject.toml`
- installazione locale consigliata in editable mode con `pip install -e ".[dev]"`
- `requirements.txt` mantenuto come entrypoint runtime minimale
- CI pronta per test, lint e type-check
