# Guida Utente DietAPP

DietAPP aiuta a costruire una settimana alimentare condivisa per due persone con regimi alimentari diversi, riducendo il lavoro in cucina e rendendo la spesa piu eseguibile.

## 1. Prima di iniziare

Prepara queste informazioni per entrambe le persone:

- nome
- regime alimentare
- eta, sesso, altezza e peso attuale
- obiettivo peso
- attivita motoria descritta in modo libero
- cibi da evitare, allergie o intolleranze
- eventuale disponibilita a usare proteine in polvere

## 2. Compilare il profilo

Nella schermata principale inserisci i dati delle due persone e poi completa le preferenze di casa:

- budget
- tempo massimo per singolo pasto
- quanti pranzi vuoi coprire con avanzi
- giorni di batch cooking
- cucine preferite
- ingredienti gia disponibili in dispensa
- ingredienti esclusi in casa
- note per il planner

Se premi `Salva profilo coppia`, l'app memorizza i valori correnti:

- in locale, se Supabase non e configurato
- nel cloud personale, se accedi con Supabase

## 3. Generare la strategia benessere

Il primo passo operativo e sempre `Genera o aggiorna strategia`.

La strategia serve per:

- stimare focus realistici per ciascuna persona
- derivare target orientativi di calorie e proteine
- fissare principi condivisi di cucina e organizzazione

Se cambi il profilo, conviene rigenerare la strategia prima di rigenerare la dieta.

## 4. Generare la dieta settimanale

Dopo aver approvato la strategia, usa `Genera dieta da questa strategia`.

La dieta settimanale mostra:

- colazione, pranzo e cena per 7 giorni
- una base comune quando possibile
- la variante della persona 1 e della persona 2
- indicazioni di riuso e lavoro in cucina

## 5. Capire porzioni e quantita

Ogni variante pasto ora espone:

- una etichetta porzione, per esempio `1 porzione pranzo`
- ingredienti con quantita e unita, per esempio `80 g riso`, `150 g pollo`, `2 pz uova`

Queste quantita sono pensate per rendere il piano piu operativo.
Se il piano viene dal fallback locale, le quantita vengono inferite automaticamente.
Se il piano arriva da AI ma il payload e incompleto, l'app prova comunque a ricostruire un dettaglio utile.

## 6. Lista della spesa

La scheda `Spesa` aggrega gli ingredienti per categoria e somma le quantita quando possibile.

Questo ti permette di passare da un piano qualitativo a una lista acquisti piu concreta.

## 7. Controlli automatici

Nella sezione `Prep e download` trovi anche i `Controlli automatici`.

Servono a segnalare rapidamente se:

- il piano non copre tutti i 7 giorni
- una o piu cene superano il vincolo principale di prep
- mancano dettagli quantitativi su alcuni pasti

Se tutto e coerente, l'app mostra un messaggio di controllo superato.

## 8. Download del piano

Puoi scaricare:

- Markdown: utile da leggere, condividere o stampare
- JSON: utile se vuoi riusare il piano in altri sistemi o conservarlo in forma strutturata

## 9. Se usi modelli gratuiti

Se usi la configurazione AI gratuita consigliata oggi:

- il modello principale e `google/gemma-4-31b-it:free`
- il primo fallback consigliato e `google/gemma-4-26b-a4b-it:free`
- i fallback successivi consigliati sono `qwen/qwen3-next-80b-a3b-instruct:free`, `openai/gpt-oss-120b:free` e `openai/gpt-oss-20b:free`

In pratica:

- OpenRouter prova prima il modello principale
- se il modello gratuito e saturo, passa ai fallback in ordine
- se hai configurato anche Groq, l'app puo usarlo come provider secondario
- se anche i provider AI non rispondono, l'app passa al planner locale

## 10. Accesso cloud con Supabase

Se l'istanza usa Supabase:

- l'app chiede login prima di mostrare il planner
- il profilo viene salvato per account
- strategia e dieta vengono ricaricate automaticamente se il profilo non e cambiato

Se ricevi un link di recovery password via email, aprilo e completa il reset direttamente nell'app.

## 11. Problemi comuni

- Hai cambiato il profilo ma vedi ancora un piano vecchio: salva il profilo e rigenera prima la strategia, poi la dieta.
- Mancano chiavi AI: l'app continua a funzionare con il planner locale.
- Un modello gratuito risulta temporaneamente limitato o saturo: l'app prova i fallback configurati; se non bastano, passa al planner locale.
- La lista della spesa non sembra completa: controlla la sezione `Controlli automatici` e rigenera il piano se il payload AI e parziale.
- Hai dubbi sulle quantita: usa il piano come base operativa e ritocca manualmente i casi in cui conosci fabbisogni molto specifici.

## 12. Nota importante

DietAPP e uno strumento organizzativo e non sostituisce indicazioni mediche o nutrizionali professionali.
