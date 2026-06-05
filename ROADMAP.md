# Piano di Evoluzione DietAPP

Questo file e il backlog operativo del progetto. L'idea e semplice: chiudere una milestone alla volta, con tagli piccoli e verificabili, senza aprire troppi fronti insieme.

Ordine consigliato: 1 -> 6.

## Milestone 1 - Baseline Tecnica

Obiettivo: rendere il progetto piu semplice da eseguire, verificare e far crescere senza workaround locali.

- [x] Creare un `pyproject.toml` e formalizzare il package `dietapp`
- [x] Installare il progetto in editable mode e rimuovere il `sys.path.insert(...)` da `app.py`
- [x] Definire un set unico di comandi di sviluppo: run, test, lint, type-check
- [x] Aggiungere Ruff con un set minimo di regole condivise
- [x] Aggiungere type-checking sui moduli core
- [x] Aggiungere una pipeline CI che esegua almeno test, lint e type-check
- [x] Aggiornare il README con setup e comandi reali di sviluppo

### Criteri di uscita

- [x] L'app parte senza manipolare il path a runtime
- [x] La suite test resta verde
- [x] Lint e type-check sono verdi in locale e in CI

## Milestone 2 - Rifattorizzare app.py

Obiettivo: trasformare `app.py` in un orchestration layer sottile e leggibile.

- [x] Estrarre tema e stile in un modulo dedicato
- [x] Estrarre helper del form e costruzione del `PlanningRequest`
- [x] Estrarre il flusso auth e Supabase dal corpo principale della pagina
- [x] Estrarre il rendering di strategia, settimana, spesa e prep in moduli UI dedicati
- [x] Centralizzare la gestione di `st.session_state`
- [x] Ridurre `app.py` a bootstrapping, wiring e orchestrazione
- [x] Aggiungere smoke test sui flussi principali dell'interfaccia

### Criteri di uscita

- [x] Le funzionalita attuali restano invariate
- [x] Il file principale e sensibilmente piu corto e piu leggibile
- [x] I flussi salva profilo, genera strategia, genera dieta e reload da cloud restano coperti

## Milestone 3 - Rifattorizzare planner.py

Obiettivo: separare regole di dominio, provider AI e catalogo pasti.

- [x] Estrarre il layer client e provider AI
- [x] Estrarre prompt, schema e normalizzazione delle risposte AI
- [x] Estrarre le euristiche locali di benessere e nutrizione
- [x] Estrarre cataloghi e template di colazioni, pranzi e cene
- [x] Estrarre sostituzioni ingredienti, filtri vincoli e adattamento template
- [x] Estrarre shopping list, prep tasks e note operative
- [x] Mantenere stabili le API pubbliche del planner o cambiarle in modo controllato

### Criteri di uscita

- [x] Le API esterne restano stabili o hanno una migrazione chiara
- [x] La suite esistente resta verde
- [x] I nuovi moduli hanno responsabilita chiare e test dedicate

## Milestone 4 - Copertura Test e Affidabilita

Obiettivo: coprire i flussi oggi meno protetti e ridurre la dipendenza da verifica manuale.

- [x] Aggiungere test dei flussi auth: login, restore session, sign-out e recovery password
- [x] Aggiungere test dell'interfaccia Streamlit con gli strumenti di testing del framework o equivalenti
- [x] Aggiungere test end-to-end del flusso profilo -> strategia -> dieta -> persistenza -> reload
- [x] Aggiungere test di regressione sulla normalizzazione AI con payload incompleti o malformati
- [x] Aggiungere snapshot o golden tests per export Markdown e JSON
- [x] Aggiungere casi limite per ingredienti esclusi, allergie e obiettivi peso

### Criteri di uscita

- [x] I flussi core non dipendono piu solo da verifica manuale
- [x] Ogni bug fix nuovo arriva con il suo test di regressione

## Milestone 5 - Evoluzione di Prodotto

Obiettivo: far passare il piano da qualitativo a operativo.

- [x] Estendere i modelli per includere porzioni, quantita e unita di misura
- [x] Aggiornare il planner locale per generare quantita sensate per persona
- [x] Aggiornare prompt AI e normalizzazione per accettare ed emettere quantita
- [x] Aggregare la lista della spesa per quantita totali e unita coerenti
- [x] Mostrare porzioni e quantita nella UI della settimana
- [x] Aggiornare export Markdown e JSON con dati piu utili all'esecuzione
- [x] Introdurre controlli minimi di coerenza sul piano generato

### Criteri di uscita

- [x] La lista della spesa e davvero usabile per fare acquisti
- [x] Ogni pasto ha abbastanza dettaglio da essere cucinato senza interpretazioni pesanti
- [x] I nuovi dati sono retrocompatibili o migrati correttamente

## Milestone 6 - Solidita Supabase e Deploy

Obiettivo: eliminare gli attriti operativi lato cloud.

- [x] Rendere lo schema Supabase idempotente anche sulle policy
- [x] Separare chiaramente setup iniziale e aggiornamenti schema
- [x] Verificare RLS e flussi di errore lato profilo, strategia e piano
- [x] Documentare setup, recovery password e deploy privato in modo piu operativo
- [x] Valutare una strategia di migrazioni versionate

### Criteri di uscita

- [x] Il setup su un nuovo progetto Supabase e ripetibile
- [x] Il rerun dello script non fallisce per oggetti gia esistenti
- [x] Gli errori cloud principali sono comprensibili e riproducibili

## Sequenza di implementazione consigliata

- [x] 1.1 Baseline tecnica minima
- [x] 2.1 Primo taglio di refactor di `app.py`
- [x] 4.1 Smoke test minimi su UI e auth
- [x] 3.1 Primo taglio di refactor di `planner.py`
- [x] 4.2 Regressioni planner e normalizzazione AI
- [x] 5.1 Evoluzione del modello dati per quantita e porzioni
- [x] 5.2 UI, export e spesa aggregata con quantita
- [x] 6.1 Hardening Supabase

## Regole operative

- [ ] Lavorare su una milestone alla volta, salvo task piccoli e indipendenti
- [ ] Ogni refactor deve lasciare comportamento invariato o avere una migrazione esplicita
- [ ] Ogni modifica strutturale deve essere accompagnata da validazione automatica
- [ ] Evitare nuove feature di prodotto prima di aver chiuso la baseline tecnica minima