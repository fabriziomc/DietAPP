# DietAPP

Applicazione web in Python + Streamlit per pianificare la dieta settimanale di una coppia con regimi alimentari diversi, riducendo al minimo il lavoro in cucina.

## Cosa fa

- raccoglie i profili alimentari di due persone
- raccoglie anche eta, sesso, altezza, peso, obiettivo peso, attivita motoria descrittiva e l'eventuale uso per-persona di proteine in polvere
- genera prima una strategia benessere personalizzata e poi il piano settimanale con colazione, pranzo e cena
- cerca di riusare basi comuni tra versione onnivora e vegetariana
- privilegia batch cooking, avanzi intelligenti e ingredienti ricorrenti
- produce una lista della spesa aggregata
- usa i valori del file `.env` per OpenAI o Groq, altrimenti passa a un planner locale deterministico con ricette italiane
- puo salvare localmente il profilo della coppia e ricaricarlo ai successivi avvii

## Avvio rapido

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

## Configurazione AI

Se vuoi usare il generatore AI:

1. imposta `AI_PROVIDER=openai` oppure `AI_PROVIDER=groq` nel file `.env`
2. se usi OpenAI compila `OPENAI_API_KEY` e opzionalmente `OPENAI_MODEL`
3. se usi Groq compila `GROQ_API_KEY` e opzionalmente `GROQ_MODEL`

Modelli consigliati su Groq per questa app:

- `llama-3.3-70b-versatile`: scelta migliore per qualita e aderenza al JSON
- `llama-3.1-8b-instant`: scelta migliore per velocita e costo ridotto

Se la chiave non e presente, l'app resta comunque utilizzabile tramite il planner locale.
Il planner locale ora filtra gli ingredienti esclusi, usa davvero budget e cucine preferite per ordinare i template, mantiene le proposte in un perimetro di ricette italiane domestiche e, nei casi piu stretti, prova a sostituire automaticamente gli ingredienti vietati con equivalenti compatibili.

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

Quando Supabase e configurato:

- l'app chiede login prima di mostrare il planner
- il profilo coppia viene salvato per `user_id` nel database
- l'ultima strategia benessere e l'ultimo piano settimanale vengono salvati e ricaricati automaticamente se il profilo non e cambiato
- i dati non dipendono piu dal filesystem locale di Streamlit Cloud

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
- `supabase/schema.sql`: tabella e policy RLS per profilo, strategia e piano utente
- `tests/test_planner.py`: test base del planner locale
