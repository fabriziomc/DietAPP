# DietAPP

Applicazione web in Python + Streamlit per pianificare la dieta settimanale di una coppia con regimi alimentari diversi, riducendo al minimo il lavoro in cucina.

## Cosa fa

- raccoglie i profili alimentari di due persone
- raccoglie anche eta, sesso, altezza, peso e attivita motoria descrittiva
- genera prima una strategia benessere personalizzata e poi il piano settimanale con colazione, pranzo e cena
- cerca di riusare basi comuni tra versione onnivora e vegetariana
- privilegia batch cooking, avanzi intelligenti e ingredienti ricorrenti
- produce una lista della spesa aggregata
- usa i valori del file `.env` per OpenAI o Groq, altrimenti passa a un generatore locale deterministico
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

## Profilo salvato

Dentro l'app puoi usare il pulsante `Salva profilo coppia`.
I valori dei due profili e delle preferenze di cucina vengono salvati localmente in `data/household_profile.json` e ricaricati automaticamente dopo refresh o riavvio.

## Nuovo flusso

1. inserisci per ciascuna persona dati fisici, regime alimentare, attivita motoria e vincoli alimentari
2. l'app genera una strategia benessere con focus e target derivati
3. da quella strategia costruisce il piano settimanale condiviso per la coppia

## Struttura

- `app.py`: interfaccia Streamlit
- `src/dietapp/models.py`: modelli dati
- `src/dietapp/planner.py`: generazione piano AI + fallback locale
- `src/dietapp/formatters.py`: export markdown e metriche
- `tests/test_planner.py`: test base del planner locale
