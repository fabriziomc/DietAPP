from __future__ import annotations

DAYS = [
    "Lunedi",
    "Martedi",
    "Mercoledi",
    "Giovedi",
    "Venerdi",
    "Sabato",
    "Domenica",
]

CUISINE_OPTIONS = [
    "Mediterranea",
    "Medio Oriente",
    "Tex-Mex",
    "Indiana",
    "Asiatica",
    "Comfort food leggera",
    "Bowl proteiche",
]

PANTRY_OPTIONS = [
    "Avena",
    "Riso",
    "Pasta",
    "Farro",
    "Legumi in barattolo",
    "Pomodori pelati",
    "Uova",
    "Yogurt greco",
    "Frutta secca",
    "Tortillas",
    "Tofu",
    "Formaggi freschi",
]

BREAKFAST_TEMPLATES = [
    {
        "shared_base": "Overnight oats con yogurt, frutta e semi",
        "omnivore_title": "Overnight oats con yogurt greco",
        "vegetarian_title": "Overnight oats con yogurt greco e semi",
        "description": "Stessa base per entrambi, con topping modulabile e zero cottura.",
        "ingredients": ["avena", "yogurt greco", "frutti di bosco", "semi di chia", "banana"],
        "prep_notes": "Prepara 2-3 vasetti in blocco la sera prima.",
        "shopping": {
            "Colazione": ["avena", "yogurt greco", "banana", "frutti di bosco", "semi di chia"],
        },
    },
    {
        "shared_base": "Toast integrale con crema spalmabile e frutta",
        "omnivore_title": "Toast con ricotta, miele e noci",
        "vegetarian_title": "Toast con ricotta, miele e noci",
        "description": "Colazione rapida da montare in 5 minuti con ingredienti ricorrenti.",
        "ingredients": ["pane integrale", "ricotta", "miele", "noci", "mela"],
        "prep_notes": "Tieni gia porzionate frutta e frutta secca.",
        "shopping": {
            "Colazione": ["pane integrale", "ricotta", "miele", "noci", "mele"],
        },
    },
    {
        "shared_base": "Yogurt bowl con granola e frutta croccante",
        "omnivore_title": "Yogurt bowl proteica",
        "vegetarian_title": "Yogurt bowl proteica",
        "description": "Una bowl fredda che riduce pulizia e padelle al minimo.",
        "ingredients": ["yogurt greco", "granola", "pera", "mandorle", "cannella"],
        "prep_notes": "Assembla al momento in una ciotola unica.",
        "shopping": {
            "Colazione": ["granola", "pere", "mandorle", "cannella"],
        },
    },
]

DINNER_BLUEPRINTS = [
    {
        "name": "Teglia mediterranea",
        "shared_base": "Verdure al forno, patate croccanti e salsa allo yogurt alle erbe",
        "omnivore": {
            "title": "Pollo al limone in teglia",
            "description": "Il pollo cuoce insieme alle verdure senza creare una seconda linea di lavoro.",
            "ingredients": ["petto di pollo", "zucchine", "peperoni", "cipolla rossa", "patate", "yogurt", "limone"],
            "prep_notes": "Condisci tutto in una bowl e inforna in un'unica teglia.",
        },
        "vegetarian": {
            "title": "Ceci e halloumi al limone in teglia",
            "description": "Stessa base di cottura, con proteina vegetariana aggiunta negli ultimi minuti.",
            "ingredients": ["ceci", "halloumi", "zucchine", "peperoni", "cipolla rossa", "patate", "limone"],
            "prep_notes": "Aggiungi halloumi a fine cottura per mantenerlo dorato.",
        },
        "prep_minutes": 30,
        "leftover_friendly": True,
        "reuse_from_previous": "Cuoci doppia dose di verdure per i bowl del giorno dopo.",
        "kitchen_load": "Basso",
        "shopping": {
            "Verdure": ["zucchine", "peperoni", "cipolla rossa", "patate", "limoni"],
            "Proteine": ["petto di pollo", "ceci", "halloumi"],
            "Frigo": ["yogurt greco"],
            "Dispensa": ["olio evo", "origano", "paprika"],
        },
    },
    {
        "name": "Curry smart",
        "shared_base": "Curry cremoso di verdure con riso basmati gia cotto in batch",
        "omnivore": {
            "title": "Curry di tacchino e spinaci",
            "description": "Una sola padella: il tacchino si unisce alla base comune negli ultimi minuti.",
            "ingredients": ["macinato di tacchino", "latte di cocco", "spinaci", "carote", "piselli", "riso basmati"],
            "prep_notes": "Rosola il tacchino nella stessa casseruola del curry.",
        },
        "vegetarian": {
            "title": "Curry di tofu croccante e spinaci",
            "description": "La base resta uguale, il tofu entra a cubi gia rosolati o in forno.",
            "ingredients": ["tofu", "latte di cocco", "spinaci", "carote", "piselli", "riso basmati"],
            "prep_notes": "Cuoci il tofu in friggitrice ad aria o al forno mentre sobbolle il curry.",
        },
        "prep_minutes": 25,
        "leftover_friendly": True,
        "reuse_from_previous": "Prepara riso extra per i pranzi del giorno seguente.",
        "kitchen_load": "Medio",
        "shopping": {
            "Verdure": ["spinaci", "carote", "piselli", "aglio", "cipolla"],
            "Proteine": ["macinato di tacchino", "tofu"],
            "Dispensa": ["riso basmati", "latte di cocco", "pasta curry", "zenzero"],
        },
    },
    {
        "name": "Ragu doppio uso",
        "shared_base": "Sugo ricco al pomodoro con soffritto, lenticchie e pasta corta",
        "omnivore": {
            "title": "Pasta al ragu misto leggero",
            "description": "Il ragu usa una piccola quota di carne per una resa elevata e piu porzioni.",
            "ingredients": ["macinato magro", "lenticchie", "sedano", "carota", "cipolla", "pasta corta", "pomodori pelati"],
            "prep_notes": "Cuoci un tegame grande e conserva meta sugo per il gratin del sabato.",
        },
        "vegetarian": {
            "title": "Pasta al ragu di lenticchie",
            "description": "La base resta identica senza carne, con piu lenticchie per corpo e proteine.",
            "ingredients": ["lenticchie", "sedano", "carota", "cipolla", "pasta corta", "pomodori pelati", "parmigiano"],
            "prep_notes": "Frulla una piccola parte del ragu per una consistenza piu piena.",
        },
        "prep_minutes": 35,
        "leftover_friendly": True,
        "reuse_from_previous": "Conserva sugo extra per pranzo o pasta al forno di recupero.",
        "kitchen_load": "Medio",
        "shopping": {
            "Verdure": ["sedano", "carote", "cipolle"],
            "Proteine": ["macinato magro", "lenticchie"],
            "Dispensa": ["pasta corta", "pomodori pelati", "passata"],
            "Frigo": ["parmigiano"],
        },
    },
    {
        "name": "Taco bar rapido",
        "shared_base": "Tortillas, peperoni arrostiti, salsa yogurt-lime e insalata croccante",
        "omnivore": {
            "title": "Tacos di pollo speziato",
            "description": "Il pollo si cuoce in una sola padella e si assembla direttamente al tavolo.",
            "ingredients": ["pollo a straccetti", "tortillas", "peperoni", "lattuga", "mais", "lime"],
            "prep_notes": "Usa le verdure gia arrostite dove possibile.",
        },
        "vegetarian": {
            "title": "Tacos di fagioli neri e feta",
            "description": "Versione vegetariana con la stessa linea di assemblaggio del taco bar.",
            "ingredients": ["fagioli neri", "feta", "tortillas", "peperoni", "lattuga", "mais", "lime"],
            "prep_notes": "Scalda fagioli e tortillas in parallelo per ridurre i tempi.",
        },
        "prep_minutes": 20,
        "leftover_friendly": True,
        "reuse_from_previous": "Riusa salse e verdure arrostite del lunedi.",
        "kitchen_load": "Basso",
        "shopping": {
            "Verdure": ["lattuga", "peperoni", "lime", "pomodorini"],
            "Proteine": ["pollo a straccetti", "fagioli neri", "feta"],
            "Dispensa": ["tortillas", "mais", "cumino"],
        },
    },
    {
        "name": "Bowl di recupero",
        "shared_base": "Bowl tiepida con riso, verdure arrostite e dressing tahina-limone",
        "omnivore": {
            "title": "Bowl con uova sode e pollo avanzato",
            "description": "Pasto di recupero che evita di cucinare da zero a meta settimana.",
            "ingredients": ["riso basmati", "verdure arrostite", "uova", "pollo avanzato", "tahina", "limone"],
            "prep_notes": "Assembla a freddo o dai solo un colpo di microonde al riso.",
        },
        "vegetarian": {
            "title": "Bowl con ceci croccanti e uova sode",
            "description": "Stessa struttura, con ceci speziati e uova per una quota proteica stabile.",
            "ingredients": ["riso basmati", "verdure arrostite", "uova", "ceci", "tahina", "limone"],
            "prep_notes": "Croccantizza i ceci in forno mentre prepari il dressing.",
        },
        "prep_minutes": 15,
        "leftover_friendly": False,
        "reuse_from_previous": "Massimizza le basi gia pronte senza sporcare pentole nuove.",
        "kitchen_load": "Molto basso",
        "shopping": {
            "Proteine": ["uova"],
            "Dispensa": ["tahina"],
        },
    },
    {
        "name": "Zuppa e toast",
        "shared_base": "Zuppa rustica di pomodoro e cannellini con toast al forno",
        "omnivore": {
            "title": "Zuppa con crumble di tacchino speziato",
            "description": "Una piccola aggiunta proteica in padella sulla stessa base della zuppa.",
            "ingredients": ["cannellini", "pomodori", "carote", "sedano", "pane casereccio", "tacchino macinato"],
            "prep_notes": "Cuoci il crumble mentre la zuppa sobbolle e servi sul piatto.",
        },
        "vegetarian": {
            "title": "Zuppa con cannellini e toast al formaggio",
            "description": "Comfort food leggero che sfrutta ingredienti di dispensa e zero tecnica.",
            "ingredients": ["cannellini", "pomodori", "carote", "sedano", "pane casereccio", "scamorza"],
            "prep_notes": "Gratina il toast in forno negli ultimi 5 minuti.",
        },
        "prep_minutes": 25,
        "leftover_friendly": True,
        "reuse_from_previous": "Cuoci doppia zuppa per uno o due pranzi veloci.",
        "kitchen_load": "Basso",
        "shopping": {
            "Verdure": ["carote", "sedano", "cipolla", "pomodori"],
            "Proteine": ["tacchino macinato", "cannellini", "scamorza"],
            "Dispensa": ["pane casereccio", "brodo vegetale"],
        },
    },
    {
        "name": "Pasta al forno di chiusura",
        "shared_base": "Gratin veloce con pasta, sugo avanzato e verdure morbide",
        "omnivore": {
            "title": "Pasta al forno con ragu avanzato",
            "description": "Chiusura della settimana che valorizza il sugo preparato prima.",
            "ingredients": ["pasta", "ragu avanzato", "mozzarella", "spinaci"],
            "prep_notes": "Assembla in pirofila e gratina senza ulteriori preparazioni.",
        },
        "vegetarian": {
            "title": "Pasta al forno vegetariana con ragu di lenticchie",
            "description": "La versione vegetariana usa lo stesso schema e lo stesso forno.",
            "ingredients": ["pasta", "ragu di lenticchie avanzato", "mozzarella", "spinaci"],
            "prep_notes": "Aggiungi un mestolo d'acqua per mantenerla cremosa in forno.",
        },
        "prep_minutes": 20,
        "leftover_friendly": True,
        "reuse_from_previous": "Recupera sughi e verdure residue per svuotare il frigo.",
        "kitchen_load": "Basso",
        "shopping": {
            "Frigo": ["mozzarella"],
            "Verdure": ["spinaci"],
            "Dispensa": ["pasta"],
        },
    },
]
